param(
    [string]$UwpDeps = 'C:\bsuwp\_deps\uwpdep-src',
    [int]$Jobs = 12,
    [string]$HostCCompiler = 'clang-cl',
    [string]$HostCxxCompiler = 'clang-cl'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'upstream'
if (-not (Test-Path -LiteralPath (Join-Path $source 'configure.py'))) {
    throw 'Run tools\setup_upstream.ps1 first.'
}
if (-not (Test-Path -LiteralPath $UwpDeps)) {
    throw "UWP dependency directory was not found: $UwpDeps"
}

Push-Location $source
try {
    & py -3 configure.py --release --pgo=off
    if ($LASTEXITCODE) { throw 'Guest configuration failed.' }
    & ninja xbox_guest
    if ($LASTEXITCODE) { throw 'Guest build failed.' }
} finally {
    Pop-Location
}

$msvc = Join-Path $PSScriptRoot 'with-msvc.ps1'
& $msvc cmake --fresh -S (Join-Path $source 'port\xbox') `
    -B (Join-Path $source 'build\xbox-uwp') -G Ninja `
    -DCMAKE_BUILD_TYPE=Release "-DCMAKE_C_COMPILER=$HostCCompiler" `
    "-DCMAKE_CXX_COMPILER=$HostCxxCompiler" "-DUWP_DEPS=$UwpDeps"
if ($LASTEXITCODE) { throw 'Host configuration failed.' }
& $msvc cmake --build (Join-Path $source 'build\xbox-uwp') -j $Jobs
if ($LASTEXITCODE) { throw 'Host build failed.' }
