cmake_minimum_required(VERSION 3.24)
project(PBZHitEnhance VERSION 0.4.0 LANGUAGES CXX ASM_MASM)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "Only Windows x64 is supported")
endif()
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
find_package(Python3 REQUIRED COMPONENTS Interpreter)
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/dependencies.json" DEPENDENCIES)
string(JSON GAME_HASH GET "${DEPENDENCIES}" game exe_sha256)
string(JSON RUNTIME_HASH GET "${DEPENDENCIES}" ue4ss dll_sha256)
set(GENERATED "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${GENERATED}")
configure_file(src/build_config.hpp.in "${GENERATED}/build_config.hpp" @ONLY)
add_custom_command(
    OUTPUT "${GENERATED}/forward.asm" "${GENERATED}/exports.inc" "${GENERATED}/dwmapi.def"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/generate_proxy.py"
            "${CMAKE_CURRENT_SOURCE_DIR}/src/dwmapi_exports.json" "${GENERATED}"
    DEPENDS tools/generate_proxy.py src/dwmapi_exports.json
    VERBATIM)
add_library(dwmapi SHARED src/loader.cpp "${GENERATED}/forward.asm" "${GENERATED}/exports.inc" "${GENERATED}/dwmapi.def")
target_compile_features(dwmapi PRIVATE cxx_std_17)
target_compile_options(dwmapi PRIVATE "$<$<COMPILE_LANGUAGE:CXX>:/W4;/utf-8;/permissive-;/EHsc>")
target_include_directories(dwmapi PRIVATE "${GENERATED}")
target_link_libraries(dwmapi PRIVATE bcrypt shell32)
target_link_options(dwmapi PRIVATE "/DEF:${GENERATED}/dwmapi.def" /DYNAMICBASE /NXCOMPAT /INCREMENTAL:NO)
set_target_properties(dwmapi PROPERTIES PREFIX "" OUTPUT_NAME dwmapi)
