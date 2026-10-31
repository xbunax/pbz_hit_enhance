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
fs::path module_path(HMODULE module) {
    std::wstring text(32768,L'\0');
    DWORD length=GetModuleFileNameW(module,text.data(),static_cast<DWORD>(text.size()));
    if(!length || length>=text.size())throw std::runtime_error("module path unavailable");
    text.resize(length);return fs::path(text);
}
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
bool matches_hash(const fs::path& path,const char *expected) {
    std::vector<unsigned char> buffer(1024*1024);
    HANDLE file=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_SEQUENTIAL_SCAN,nullptr);
    if(file==INVALID_HANDLE_VALUE)return false;
    BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;bool valid=false;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0 && BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)>=0) {
        DWORD count=0;bool read_ok=true;
        for(;;) {
            if(!ReadFile(file,buffer.data(),static_cast<DWORD>(buffer.size()),&count,nullptr)){read_ok=false;break;}
            if(!count)break;
            if(BCryptHashData(hash,buffer.data(),count,0)<0){read_ok=false;break;}
        }
        unsigned char digest[32];
        if(read_ok && BCryptFinishHash(hash,digest,sizeof(digest),0)>=0) {
            char hex[65];constexpr char digits[]="0123456789abcdef";
            for(int i=0;i<32;++i){hex[2*i]=digits[digest[i]>>4];hex[2*i+1]=digits[digest[i]&15];}hex[64]=0;
            valid=strcmp(hex,expected)==0;
        }
    }
    if(hash)BCryptDestroyHash(hash);
    if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);
    CloseHandle(file);return valid;
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
std::wstring quote(const fs::path& path) {
    // Windows file names cannot contain double quotes. Duplicate trailing backslashes before a closing quote.
    auto value=path.wstring();size_t trailing=0;
    for(auto i=value.rbegin();i!=value.rend() && *i==L'\\';++i)++trailing;
    return L"\""+value+std::wstring(trailing,L'\\')+L"\"";
}
std::vector<wchar_t> child_environment(const fs::path& temporary) {
    std::vector<std::wstring> entries;LPWCH environment=GetEnvironmentStringsW();
    if(environment) {
        for(const wchar_t *p=environment;*p;p+=wcslen(p)+1)
            if(_wcsnicmp(p,L"TEMP=",5)!=0 && _wcsnicmp(p,L"TMP=",4)!=0)entries.emplace_back(p);
        FreeEnvironmentStringsW(environment);
    }
    entries.emplace_back(L"TEMP="+temporary.wstring());entries.emplace_back(L"TMP="+temporary.wstring());
    std::sort(entries.begin(),entries.end(),[](const auto&a,const auto&b){return _wcsicmp(a.c_str(),b.c_str())<0;});
    std::vector<wchar_t> block;
    for(const auto&entry:entries){block.insert(block.end(),entry.begin(),entry.end());block.push_back(0);}
    block.push_back(0);return block;
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
        HMODULE runtime=GetModuleHandleW(L"UE4SS.dll");
        if(runtime) {
            if(_wcsicmp(module_path(runtime).c_str(),runtime_path.c_str())!=0){set_status(Status::other_runtime);record(root,"other_ue4ss_instance_skipped");return 0;}
        } else runtime=LoadLibraryW(runtime_path.c_str());
        if(!runtime){set_status(Status::runtime_failed);record(root,"runtime_load_failed",GetLastError());return 0;}
        set_status(Status::runtime_loaded);record(root,"runtime_loaded");
        const auto executable=root/L"panel"/L"HitstopPanel.exe";
        const auto mod=root/L"ue4ss"/L"Mods"/L"UnifiedHitstop";
        fs::create_directories(root/L"temp");
        auto environment=child_environment(root/L"temp");
        std::wstring command=quote(executable)+L" --auto-start --mod-dir "+quote(mod);
        STARTUPINFOW startup{};startup.cb=sizeof(startup);PROCESS_INFORMATION process{};
        if(CreateProcessW(executable.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW|CREATE_UNICODE_ENVIRONMENT,environment.data(),root.c_str(),&startup,&process)) {
            set_status(Status::panel_started);record(root,"panel_started",process.dwProcessId);
            CloseHandle(process.hThread);CloseHandle(process.hProcess);
        } else {set_status(Status::panel_failed);record(root,"panel_start_failed",GetLastError());}
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
