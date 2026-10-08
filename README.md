# OpenCE UWP

This project ports [OpenCE](https://github.com/OpenCommunityEdition/OpenCE) to x64 UWP for Xbox Developer Mode. The retail game is not included.

At first launch, select internal or external storage and choose a legally owned Halo: Combat Evolved Xbox ISO or XISO. The launcher extracts the required game files and remembers the installation. Later launches start the game automatically; the storage menu returns if the installation is unavailable.

## Build

Install Visual Studio 2022 with the C++ UWP tools, Windows SDK 10.0.26100, Python, Ninja, CMake, Clang, and LLD. The build also requires x64 UWP builds of SDL2, libuwp, Mesa, and zlib.

```powershell
./tools/setup_upstream.ps1
./tools/build.ps1 -UwpDeps C:/path/to/uwp-deps
./tools/make_release.ps1
```

Install `OpenCE-UWP-x64.appx` through Xbox Device Portal. Add `Dependencies/x64/Microsoft.VCLibs.x64.14.00.appx` if the portal requests it.

## Xbox storage

- **Internal:** place the ISO or XISO in `LocalState`, then select **Internal Storage**. Game files, saves, settings, caches, and logs use `LocalState\OpenCE`.
- **External:** select **External Storage** and browse the connected drive. Game files, saves, settings, caches, and logs use the drive's `OpenCE` folder.

## License

See [LICENSE.md](LICENSE.md). Halo: Combat Evolved is copyright Microsoft. No retail game data is included.
