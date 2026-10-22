#!/usr/bin/env bash
# Install talkicut as an agent skill: copies this folder into the skills directory.
# Usage: ./install.sh [target-skills-dir]
set -euo pipefail

src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:-$HOME/.config/opencode/skills}"
dest="$target/talkicut"

mkdir -p "$target"
if [ -e "$dest" ]; then
  echo "already installed: $dest"
  echo "remove it first, or clone the repo directly into that path to upgrade:"
  echo "  git clone https://github.com/laopro/talkicut.git \"$dest\""
  exit 1
fi

cp -R "$src" "$dest"
rm -rf "$dest/.git"   # a copy is not a clone
echo "talkicut installed in $dest"
echo
echo "check the machine:  python3 \"$dest/scripts/talkicut.py\" doctor"
echo "prove it works:     python3 \"$dest/scripts/talkicut.py\" selftest"
