cmake_minimum_required(VERSION 3.24)
set(CMAKE_SYSTEM_NAME WindowsStore)
set(CMAKE_SYSTEM_VERSION 10.0.26100.0 CACHE STRING "Xbox UWP SDK")
if(EXISTS "$ENV{VCToolsInstallDir}/bin/Hostx64/x64/link.exe")
  set(CMAKE_LINKER "$ENV{VCToolsInstallDir}/bin/Hostx64/x64/link.exe" CACHE FILEPATH "UWP metadata linker" FORCE)
endif()
project(OpenCEUWP LANGUAGES C CXX ASM_MASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)

get_filename_component(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(UWP_DEPS "C:/bsuwp/_deps/uwpdep-src" CACHE PATH "SDL2/libuwp/Mesa UWP bundle")
set(GENERATED "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${GENERATED}")

find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_custom_command(OUTPUT "${GENERATED}/host_gl.c"
  COMMAND "${Python3_EXECUTABLE}" "${REPO_ROOT}/tools/xbox_host_gl.py"
    "${REPO_ROOT}/build/xbox/guest/gen/guest_gl.c" "${GENERATED}/host_gl.c"
  DEPENDS "${REPO_ROOT}/tools/xbox_host_gl.py" "${REPO_ROOT}/build/xbox/guest/gen/guest_gl.c")
add_custom_command(OUTPUT "${GENERATED}/host_posix.c"
  COMMAND "${Python3_EXECUTABLE}" "${REPO_ROOT}/tools/xbox_host_posix.py"
    "${REPO_ROOT}/build/xbox/guest/gen/guest_posix.c" "${GENERATED}/host_posix.c"
  DEPENDS "${REPO_ROOT}/tools/xbox_host_posix.py" "${REPO_ROOT}/build/xbox/guest/gen/guest_posix.c")

set(HOST_SOURCES
  host/host_main.cpp host/xiso_installer.cpp host/setup_ui.cpp host/host_loader.c host/host_memory.c host/host_thread.c host/host_syscall.c host/host_sdl.c
  host/host_posix_misc.c host/guest_call.asm
  "${REPO_ROOT}/build/xbox/host/host_import_table.c"
  "${REPO_ROOT}/port/windows/src/win32_files.c"
  "${REPO_ROOT}/port/windows/src/win32_net.c"
  "${GENERATED}/host_gl.c" "${GENERATED}/host_posix.c")

set(IMGUI "${CMAKE_CURRENT_SOURCE_DIR}/third_party/imgui")
list(APPEND HOST_SOURCES
  "${IMGUI}/imgui.cpp" "${IMGUI}/imgui_draw.cpp" "${IMGUI}/imgui_tables.cpp" "${IMGUI}/imgui_widgets.cpp"
  "${IMGUI}/backends/imgui_impl_sdl2.cpp" "${IMGUI}/backends/imgui_impl_opengl3.cpp")

set(WINRT_ENTRY "${CMAKE_CURRENT_BINARY_DIR}/winrt_main.obj")
add_custom_command(OUTPUT "${WINRT_ENTRY}"
  COMMAND cl.exe /nologo /TP /ZW /EHsc /DWINAPI_FAMILY=WINAPI_FAMILY_APP /DNOMINMAX
    /I"${UWP_DEPS}/x64/include/SDL2" /Fo"${WINRT_ENTRY}" /c "${CMAKE_CURRENT_SOURCE_DIR}/host/winrt_main.cpp"
  DEPENDS host/winrt_main.cpp)
set_source_files_properties("${WINRT_ENTRY}" PROPERTIES EXTERNAL_OBJECT TRUE GENERATED TRUE)

add_executable(OpenCEUWP WIN32 ${HOST_SOURCES} "${WINRT_ENTRY}")
set_target_properties(OpenCEUWP PROPERTIES OUTPUT_NAME "OpenCE UWP")
target_compile_definitions(OpenCEUWP PRIVATE WINAPI_FAMILY=WINAPI_FAMILY_APP NOMINMAX
  _CRT_SECURE_NO_WARNINGS _ALLOW_COMPILER_AND_STL_VERSION_MISMATCH
  HALO_GUEST_IMAGE_BASE=0x70000000u)
target_compile_options(OpenCEUWP PRIVATE $<$<COMPILE_LANGUAGE:C,CXX>:/W3>)
target_include_directories(OpenCEUWP PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/host"
  "${REPO_ROOT}/port/android/include"
  "${REPO_ROOT}/port/linux/src"
  "${IMGUI}" "${IMGUI}/backends"
  "${UWP_DEPS}/x64/include" "${UWP_DEPS}/x64/include/SDL2")
target_link_directories(OpenCEUWP BEFORE PRIVATE "$ENV{VCToolsInstallDir}/lib/x64/store")
target_link_libraries(OpenCEUWP PRIVATE WindowsApp bcrypt ws2_32 iphlpapi
  "${UWP_DEPS}/x64/lib/SDL2.lib" "${UWP_DEPS}/x64/lib/libuwp.lib")
target_link_options(OpenCEUWP PRIVATE /APPCONTAINER /WINMD
  "/WINMDFILE:${CMAKE_CURRENT_BINARY_DIR}/OpenCEUWP.winmd")

foreach(runtime SDL2.dll libuwp.dll opengl32.dll libgallium_wgl.dll dxil.dll z-1.dll)
  add_custom_command(TARGET OpenCEUWP POST_BUILD COMMAND "${CMAKE_COMMAND}" -E copy_if_different
    "${UWP_DEPS}/x64/bin/${runtime}" "$<TARGET_FILE_DIR:OpenCEUWP>/${runtime}")
endforeach()
add_custom_command(TARGET OpenCEUWP POST_BUILD COMMAND "${CMAKE_COMMAND}" -E copy_if_different
  "${REPO_ROOT}/build/xbox/halo_guest.elf" "$<TARGET_FILE_DIR:OpenCEUWP>/halo_guest.elf")
