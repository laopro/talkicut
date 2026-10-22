param(
    [string]$Target = "$HOME\.config\opencode\skills"
)

# Install talkicut as an agent skill: copies this folder into the skills directory.
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $Target "talkicut"

New-Item -ItemType Directory -Force -Path $Target | Out-Null
if (Test-Path $dest) {
    Write-Error "already installed: $dest. Remove it first, or clone the repo there to upgrade."
    exit 1
}

Copy-Item -Recurse -Path $src -Destination $dest
Write-Host "talkicut installed in $dest"
Write-Host ""
Write-Host "check the machine:  python `"$dest\scripts\talkicut.py`" doctor"
Write-Host "prove it works:     python `"$dest\scripts\talkicut.py`" selftest"
