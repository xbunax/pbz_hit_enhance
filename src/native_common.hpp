#pragma once
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <bcrypt.h>
#include <algorithm>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs = std::filesystem;
fs::path module_path(HMODULE module) {
    std::wstring text(32768,L'\0');
    DWORD length=GetModuleFileNameW(module,text.data(),static_cast<DWORD>(text.size()));
    if(!length || length>=text.size())throw std::runtime_error("module path unavailable");
    text.resize(length);return fs::path(text);
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

inline std::string utf8(const std::wstring& value) {
    int size=WideCharToMultiByte(CP_UTF8,0,value.data(),static_cast<int>(value.size()),nullptr,0,nullptr,nullptr);
    std::string out(size,'\0');
    if(size)WideCharToMultiByte(CP_UTF8,0,value.data(),static_cast<int>(value.size()),out.data(),size,nullptr,nullptr);
    return out;
}
inline unsigned long long creation_time(HANDLE process) {
    FILETIME created{},exit{},kernel{},user{};
    if(!GetProcessTimes(process,&created,&exit,&kernel,&user))throw std::runtime_error("process time unavailable");
    return (static_cast<unsigned long long>(created.dwHighDateTime)<<32)|created.dwLowDateTime;
}

struct JobChild { HANDLE job; DWORD pid; };
inline JobChild launch_in_job(const fs::path& executable,std::wstring command,const fs::path& working,std::vector<wchar_t>& environment) {
    HANDLE job=CreateJobObjectW(nullptr,nullptr);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if(!job || !SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits))) {
        if(job)CloseHandle(job);throw std::runtime_error("panel_job_failed");
    }
    STARTUPINFOW startup{};startup.cb=sizeof(startup);PROCESS_INFORMATION process{};
    if(!CreateProcessW(executable.c_str(),command.data(),nullptr,nullptr,FALSE,CREATE_SUSPENDED|CREATE_NO_WINDOW|CREATE_UNICODE_ENVIRONMENT,environment.data(),working.c_str(),&startup,&process)) {
        CloseHandle(job);throw std::runtime_error("panel_create_failed");
    }
    if(!AssignProcessToJobObject(job,process.hProcess) || ResumeThread(process.hThread)==static_cast<DWORD>(-1)) {
        TerminateProcess(process.hProcess,1);CloseHandle(process.hThread);CloseHandle(process.hProcess);CloseHandle(job);throw std::runtime_error("panel_job_assignment_failed");
    }
    DWORD pid=process.dwProcessId;CloseHandle(process.hThread);CloseHandle(process.hProcess);return {job,pid};
}
