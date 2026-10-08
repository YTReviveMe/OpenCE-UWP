param(
    [string]$SourceDirectory,
    [string]$Repository = 'https://github.com/OpenCommunityEdition/OpenCE.git',
    [string]$Revision = 'ff47e47ad6f54bc533cee2a0fe57232c8f63d614',
    [string]$ImGuiSource
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $SourceDirectory) { $SourceDirectory = Join-Path $root 'upstream' }
$SourceDirectory = [IO.Path]::GetFullPath($SourceDirectory)
if (Test-Path -LiteralPath $SourceDirectory) {
    throw "Source directory already exists: $SourceDirectory"
}

& git clone --no-checkout $Repository $SourceDirectory
if ($LASTEXITCODE) { throw 'OpenCE clone failed.' }
& git -C $SourceDirectory checkout --detach $Revision
if ($LASTEXITCODE) { throw "OpenCE revision was not found: $Revision" }

$patch = Join-Path $root 'patches\opence-uwp.patch'
& git -C $SourceDirectory apply --check $patch
if ($LASTEXITCODE) { throw 'OpenCE UWP patch validation failed.' }
& git -C $SourceDirectory apply $patch
if ($LASTEXITCODE) { throw 'OpenCE UWP patch failed.' }

$portDestination = Join-Path $SourceDirectory 'port\xbox'
New-Item -ItemType Directory -Path $portDestination -Force | Out-Null
Copy-Item -Path (Join-Path $root 'UWP\xbox\*') -Destination $portDestination -Recurse -Force

$toolNames = @(
    'generate_xbox_assets.ps1', 'musl_headers.py', 'package_xbox.ps1',
    'sign_xbox.ps1', 'xbox_build.py',
    'xbox_host_gl.py', 'xbox_host_posix.py'
)
foreach ($name in $toolNames) {
    Copy-Item -LiteralPath (Join-Path $root "tools\$name") `
        -Destination (Join-Path $SourceDirectory "tools\$name") -Force
}

$imguiDestination = Join-Path $portDestination 'third_party\imgui'
New-Item -ItemType Directory -Path (Split-Path -Parent $imguiDestination) -Force | Out-Null
if ($ImGuiSource) {
    Copy-Item -LiteralPath $ImGuiSource -Destination $imguiDestination -Recurse
} else {
    & git clone --depth 1 --branch v1.91.9b https://github.com/ocornut/imgui.git $imguiDestination
    if ($LASTEXITCODE) { throw 'Dear ImGui clone failed.' }
}

Write-Output "Prepared $SourceDirectory"
