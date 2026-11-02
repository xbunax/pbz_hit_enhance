// Test-only host: never packaged. Exercises the production Job launcher.
#include "native_common.hpp"
#include <fstream>
int wmain(int argc,wchar_t** argv) {
    if(argc!=5)return 2;
    try {
        auto env=child_environment(argv[3]);
        auto child=launch_in_job(argv[1],quote(argv[1])+L" -c \"import time;time.sleep(60)\"",argv[3],env);
        {std::ofstream out(fs::path(argv[2]),std::ios::trunc);out<<child.pid;}
        Sleep(static_cast<DWORD>(_wtoi(argv[4])));
        CloseHandle(child.job);return 0;
    } catch(...) {return 3;}
}
