param(
    [string]$Repository = 'https://github.com/OpenCommunityEdition/OpenCE.git',
    [string]$Tag
)

$ErrorActionPreference = 'Stop'
$refs = & git ls-remote --tags --refs $Repository 'refs/tags/build-*'
if ($LASTEXITCODE) { throw 'Could not read OpenCE release tags.' }

$releases = foreach ($line in $refs) {
    if ($line -match '^([0-9a-f]+)\s+refs/tags/(build-(\d+))$') {
        [pscustomobject]@{
            Commit = $Matches[1]
            Tag = $Matches[2]
            Build = [int]$Matches[3]
        }
    }
}
if (-not $releases) { throw 'No OpenCE build tags were found.' }

if ($Tag) {
    $release = $releases | Where-Object Tag -eq $Tag | Select-Object -First 1
    if (-not $release) { throw "OpenCE release tag was not found: $Tag" }
} else {
    $release = $releases | Sort-Object Build -Descending | Select-Object -First 1
}

$release | Add-Member Version ('{0}.{1}.{2}.0' -f `
    [math]::Floor($release.Build / 100),
    [math]::Floor(($release.Build % 100) / 10),
    ($release.Build % 10))
$release | ConvertTo-Json -Compress
