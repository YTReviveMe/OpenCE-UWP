#include <Windows.h>
#include <SDL_main.h>
#pragma warning(disable : 4447)
extern "C" int SDL_main(int, char **);
int CALLBACK WinMain(HINSTANCE, HINSTANCE, LPSTR, int) { return SDL_WinRTRunApp(SDL_main, nullptr); }
