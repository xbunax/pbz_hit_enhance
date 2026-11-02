#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
#include <bcrypt.h>
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <string>
#include <vector>
#include "build_config.hpp"
#include "native_common.hpp"

namespace fs = std::filesystem;
namespace {
enum class Status : DWORD {
    waiting=0, disabled=1, not_target=2, missing_data=3, game_mismatch=4,
    runtime_mismatch=5, runtime_loaded=6, panel_started=7, panel_failed=8,
    exception=9, other_runtime=10, runtime_failed=11
};
std::atomic<DWORD> status{0};
void set_status(Status value) { status.store(static_cast<DWORD>(value)); }
// Some Windows builds do not export every optional function in the reviewed list.
HRESULT WINAPI missing_export() { return E_NOTIMPL; }
}
#include "exports.inc"
namespace {
fs::path data_directory(HMODULE self) {
    const auto directory=module_path(self).parent_path();
    std::wstring value(32768,L'\0');
    const auto ini=directory/L"PBZHitEnhance.ini";
    DWORD length=GetPrivateProfileStringW(L"Paths",L"DataDirectory",L"PBZHitEnhance",value.data(),static_cast<DWORD>(value.size()),ini.c_str());
    if(!length || length>=value.size()-1)throw std::runtime_error("invalid data directory");
    value.resize(length);fs::path path(value);
    return fs::absolute(path.is_absolute()?path:directory/path).lexically_normal();
}
void record(const fs::path& root,const char *message,DWORD code=0) {
    const auto path=root/L"logs"/L"loader.log";
    HANDLE file=CreateFileW(path.c_str(),FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(file==INVALID_HANDLE_VALUE)return;
    SYSTEMTIME time;GetLocalTime(&time);char line[512];
    int count=snprintf(line,sizeof(line),"%04u-%02u-%02u %02u:%02u:%02u pid=%lu %s code=%lu\r\n",time.wYear,time.wMonth,time.wDay,time.wHour,time.wMinute,time.wSecond,GetCurrentProcessId(),message,code);
    DWORD written=0;if(count>0 && count<sizeof(line))WriteFile(file,line,static_cast<DWORD>(count),&written,nullptr);
    CloseHandle(file);
}
bool disabled(const fs::path& root) {
    if(fs::exists(root/L"disabled.flag"))return true;
    int count=0;LPWSTR *arguments=CommandLineToArgvW(GetCommandLineW(),&count);bool result=false;
    if(arguments) {
        for(int i=1;i<count;++i)
            if(wcscmp(arguments[i],L"--disable-ue4ss")==0 || wcscmp(arguments[i],L"--disable-unified-hitstop")==0)result=true;
        LocalFree(arguments);
    }
    return result;
}
DWORD WINAPI start_mod(void *argument) {
    fs::path root;
    try {
        const auto game=module_path(nullptr);
        if(_wcsicmp(game.filename().c_str(),L"PBZ.exe")!=0){set_status(Status::not_target);return 0;}
        root=data_directory(static_cast<HMODULE>(argument));
        if(!fs::is_directory(root)){set_status(Status::missing_data);return 0;}
        fs::create_directories(root/L"logs");
        if(disabled(root)){set_status(Status::disabled);record(root,"disabled_skipped");return 0;}
        record(root,"game_start_detected");
        if(!matches_hash(game,GAME_HASH)){set_status(Status::game_mismatch);record(root,"unsupported_game_skipped");return 0;}
        const auto runtime_path=root/L"ue4ss"/L"UE4SS.dll";
        if(!matches_hash(runtime_path,RUNTIME_HASH)){set_status(Status::runtime_mismatch);record(root,"runtime_checksum_failed");return 0;}
        int count=0;LPWSTR* args=CommandLineToArgvW(GetCommandLineW(),&count);
        bool external_path=false;
        if(args){for(int i=1;i<count;++i)if(wcscmp(args[i],L"--ue4ss-path")==0 || wcsncmp(args[i],L"--ue4ss-path=",13)==0)external_path=true;LocalFree(args);}
        if(external_path){set_status(Status::other_runtime);record(root,"explicit_ue4ss_path_use_mod_only");return 0;}
        HMODULE runtime=GetModuleHandleW(L"UE4SS.dll");
        const auto directory=game.parent_path();
        for(const auto& candidate : {directory/L"UE4SS.dll",directory/L"ue4ss"/L"UE4SS.dll",directory/L"override.txt"}) {
            if(fs::exists(candidate) && fs::weakly_canonical(candidate)!=fs::weakly_canonical(runtime_path)) {
                set_status(Status::other_runtime);record(root,"external_ue4ss_installation_use_mod_only");return 0;
            }
        }
        if(runtime) {
            if(_wcsicmp(module_path(runtime).c_str(),runtime_path.c_str())!=0){set_status(Status::other_runtime);record(root,"other_ue4ss_instance_skipped");return 0;}
        } else runtime=LoadLibraryW(runtime_path.c_str());
        if(!runtime){set_status(Status::runtime_failed);record(root,"runtime_load_failed",GetLastError());return 0;}
        set_status(Status::runtime_loaded);record(root,"runtime_loaded");
        // The Lua Mod starts the panel through PBZBootstrap only after it is loaded.
    } catch(...) {set_status(Status::exception);if(!root.empty())record(root,"bootstrap_exception_skipped");}
    return 0;
}
}
extern "C" __declspec(dllexport) DWORD WINAPI PBZHitEnhanceStatus() {return status.load();}
BOOL WINAPI DllMain(HINSTANCE self,DWORD reason,LPVOID) {
    if(reason==DLL_PROCESS_ATTACH) {
        wchar_t system[MAX_PATH];UINT length=GetSystemDirectoryW(system,MAX_PATH);
        if(!length || length>=MAX_PATH)return FALSE;
        const auto original_path=fs::path(system)/L"dwmapi.dll";
        HMODULE original=LoadLibraryW(original_path.c_str());if(!original)return FALSE;
        bind_exports(original);
        HMODULE pinned=nullptr;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(self),&pinned))return FALSE;
        HANDLE worker=CreateThread(nullptr,0,start_mod,self,0,nullptr);
        if(worker)CloseHandle(worker);
    }
    return TRUE;
}
