param([string]$BuildDirectory,[string]$OutputPath)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$sourceRoot=if(Test-Path -LiteralPath (Join-Path $root 'upstream\port\xbox')){Join-Path $root 'upstream'}else{$root}
if(-not $BuildDirectory){$BuildDirectory=Join-Path $sourceRoot 'build\xbox-uwp'}
if(-not $OutputPath){$OutputPath=Join-Path $BuildDirectory 'OpenCE-Xbox-x64.appx'}
$required=@('OpenCE UWP.exe','OpenCEUWP.winmd','SDL2.dll','libuwp.dll','opengl32.dll','libgallium_wgl.dll','dxil.dll','z-1.dll','halo_guest.elf')
foreach($name in $required){if(-not(Test-Path -LiteralPath (Join-Path $BuildDirectory $name))){throw "Missing build output: $name"}}
$assets=Join-Path $BuildDirectory 'xbox-assets'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $sourceRoot 'tools\generate_xbox_assets.ps1') -OutputDirectory $assets
$makeAppx=Get-ChildItem -LiteralPath (Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin') -Recurse -Filter MakeAppx.exe | Where-Object FullName -match '\\x64\\MakeAppx.exe$' | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if(-not $makeAppx){throw 'MakeAppx.exe not found'}
$stage=Join-Path $BuildDirectory ('.stage-'+[guid]::NewGuid().ToString('N'))
try {
 New-Item -ItemType Directory -Path $stage|Out-Null
 foreach($name in $required){Copy-Item -LiteralPath (Join-Path $BuildDirectory $name) -Destination $stage}
 Copy-Item -LiteralPath (Join-Path $sourceRoot 'port\xbox\Package.appxmanifest') -Destination (Join-Path $stage 'AppxManifest.xml')
 New-Item -ItemType Directory -Path (Join-Path $stage 'Assets')|Out-Null
 Copy-Item -Path (Join-Path $assets '*.png') -Destination (Join-Path $stage 'Assets')
 New-Item -ItemType Directory -Path (Join-Path $stage 'OpenCE')|Out-Null
 Copy-Item -Path (Join-Path $sourceRoot 'port\assets\*') -Destination (Join-Path $stage 'OpenCE') -Recurse
 Copy-Item -LiteralPath (Join-Path $sourceRoot 'port\third_party\extract-xiso\LICENSE.TXT') -Destination (Join-Path $stage 'extract-xiso-LICENSE.txt')
 Copy-Item -LiteralPath (Join-Path $sourceRoot 'port\third_party\mbedtls\LICENSE') -Destination (Join-Path $stage 'mbedtls-LICENSE.txt')
 Copy-Item -LiteralPath (Join-Path $sourceRoot 'port\xbox\third_party\imgui\LICENSE.txt') -Destination (Join-Path $stage 'imgui-LICENSE.txt')
 $assetRoot=Join-Path $sourceRoot 'port\assets'
 Get-ChildItem -LiteralPath $assetRoot -Recurse -File |
  ForEach-Object { $_.FullName.Substring($assetRoot.Length + 1).Replace('\','/') } |
  Set-Content -LiteralPath (Join-Path $stage 'OpenCE-assets.txt') -Encoding Ascii
 if(Test-Path -LiteralPath $OutputPath){Remove-Item -LiteralPath $OutputPath}
 & $makeAppx pack /d $stage /p $OutputPath /o
 if($LASTEXITCODE){throw "MakeAppx failed: $LASTEXITCODE"}
} finally {if(Test-Path -LiteralPath $stage){Remove-Item -LiteralPath $stage -Recurse -Force}}
Write-Output "Created $OutputPath"
