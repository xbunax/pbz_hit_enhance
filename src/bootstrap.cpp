#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include "native_common.hpp"
#include "build_config.hpp"
#include <fstream>
#include <mutex>
#include <sstream>
#include <tlhelp32.h>
#include <shellapi.h>

namespace {
HMODULE self_module=nullptr;
HANDLE owner=nullptr;
HANDLE panel_job=nullptr;
std::mutex gate;
bool initialized=false;

void atomic_file(const fs::path& path,const std::string& text) {
    const auto pending=path.wstring()+L".pending";
    { std::ofstream out(pending,std::ios::binary|std::ios::trunc);out<<text;if(!out)throw std::runtime_error("cannot write bootstrap state"); }
    if(!MoveFileExW(pending.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("cannot commit bootstrap state");
}
std::vector<fs::path> runtimes() {
    std::vector<fs::path> paths;
    HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,GetCurrentProcessId());
    if(snap==INVALID_HANDLE_VALUE)throw std::runtime_error("module inventory unavailable");
    MODULEENTRY32W entry{};entry.dwSize=sizeof(entry);
    if(Module32FirstW(snap,&entry))do {
        if(_wcsicmp(entry.szModule,L"UE4SS.dll")==0)paths.emplace_back(entry.szExePath);
    } while(Module32NextW(snap,&entry));
    CloseHandle(snap);return paths;
}
std::string file_hash(const fs::path& path) {
    HANDLE f=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    if(f==INVALID_HANDLE_VALUE)return "unavailable";
    BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;std::string result="unavailable";
    if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0 && BCryptCreateHash(alg,&hash,nullptr,0,nullptr,0,0)>=0) {
        std::vector<unsigned char> b(1024*1024);DWORD n=0;bool ok=true;
        for(;;){if(!ReadFile(f,b.data(),static_cast<DWORD>(b.size()),&n,nullptr)){ok=false;break;}if(!n)break;if(BCryptHashData(hash,b.data(),n,0)<0){ok=false;break;}}
        unsigned char out[32];
        if(ok && BCryptFinishHash(hash,out,32,0)>=0){const char*d="0123456789abcdef";result.clear();for(auto v:out){result+=d[v>>4];result+=d[v&15];}}
    }
    if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);CloseHandle(f);return result;
}
}

// lua_CFunction ABI. No Lua/UE4SS symbols or state are accessed; no SDK ABI dependency.
extern "C" __declspec(dllexport) int luaopen_pbz_bootstrap(void*) noexcept {
    std::lock_guard<std::mutex> lock(gate);
    if(initialized)return 0;
    fs::path root;
    std::string fields;
    try {
        root=fs::weakly_canonical(module_path(self_module).parent_path().parent_path());
        fs::create_directories(root/L"temp");
        const auto game=module_path(nullptr);
        const auto created=creation_time(GetCurrentProcess());
        const auto session=std::to_wstring(GetCurrentProcessId())+L"_"+std::to_wstring(created);
        std::ifstream mode_file(root/L"install-mode.txt");std::string mode;std::getline(mode_file,mode);
        fields="[Session]\nGamePid="+std::to_string(GetCurrentProcessId())+"\nGameCreatedAt="+std::to_string(created)+"\nGameExe="+utf8(game.wstring())+"\nModDir="+utf8(root.wstring())+"\nMode="+mode+"\n";
        if(_wcsicmp(game.filename().c_str(),L"PBZ.exe")!=0 || !matches_hash(game,GAME_HASH))throw std::runtime_error("unsupported_game");
        int argc=0;auto argv=CommandLineToArgvW(GetCommandLineW(),&argc);bool disabled=false;
        if(argv){for(int i=1;i<argc;++i)if(wcscmp(argv[i],L"--disable-unified-hitstop")==0||wcscmp(argv[i],L"--disable-ue4ss")==0)disabled=true;LocalFree(argv);}
        if(disabled || fs::exists(root/L"disabled.flag"))throw std::runtime_error("disabled");
        const auto loaded=runtimes();
        if(loaded.size()!=1)throw std::runtime_error("expected_exactly_one_ue4ss");
        const auto sha=file_hash(loaded[0]);
        fields+="RuntimePath="+utf8(loaded[0].wstring())+"\nRuntimeSha256="+sha+"\nRuntimeVersion="+(sha==RUNTIME_HASH?std::string("v3.0.1-1183-gcdbc0b66"):std::string("unknown"))+"\nRuntimeVerified="+(sha==RUNTIME_HASH?"true":"false")+"\n";
        owner=CreateMutexW(nullptr,FALSE,(L"Local\\PBZ_Hitstop_Owner_"+session).c_str());
        if(!owner)throw std::runtime_error("owner_mutex_failed");
        if(GetLastError()==ERROR_ALREADY_EXISTS){CloseHandle(owner);owner=nullptr;throw std::runtime_error("duplicate_mod_instance");}
        HMODULE pinned=nullptr;
        if(!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&luaopen_pbz_bootstrap),&pinned))throw std::runtime_error("bootstrap_pin_failed");
        const auto executable=root/L"panel"/L"HitstopPanel.exe";
        if(!fs::is_regular_file(executable))throw std::runtime_error("panel_missing");
        // No inherited job handle: its final handle lives only in the game process.
        auto env=child_environment(root/L"temp");
        std::wstring command=quote(executable)+L" --auto-start --mod-dir "+quote(root)+L" --game-pid "+std::to_wstring(GetCurrentProcessId())+L" --game-created-at "+std::to_wstring(created)+L" --game-exe "+quote(game);
        auto child=launch_in_job(executable,command,root,env);
        panel_job=child.job;
        fields+="PanelPid="+std::to_string(child.pid)+"\nJobAttached=true\n";
        atomic_file(root/L"bootstrap.ini",fields+"Allowed=true\nError=\n");
        initialized=true;
    } catch(const std::exception& error) {
        if(panel_job){CloseHandle(panel_job);panel_job=nullptr;}
        if(owner){CloseHandle(owner);owner=nullptr;}
        try {if(!root.empty())atomic_file(root/L"bootstrap.ini",fields+"Allowed=false\nError="+error.what()+"\n");}catch(...){}
    } catch(...) {}
    return 0;
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID) {
    if(reason==DLL_PROCESS_ATTACH){self_module=module;DisableThreadLibraryCalls(module);}
    return TRUE;
}
