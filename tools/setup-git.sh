#!/usr/bin/env bash
# Run once per clone: enables Git LFS and Unity's smart merge for scenes/prefabs.
# Usage: tools/setup-git.sh [/path/to/UnityYAMLMerge]
set -euo pipefail

git lfs install

# Default macOS path for the project's editor version; pass your own path for other OSes.
VERSION="$(sed -n 's/^m_EditorVersion: //p' ProjectSettings/ProjectVersion.txt)"
EDITOR_DIR="/Applications/Unity/Hub/Editor/$VERSION/Unity.app/Contents"
DRIVER="${1:-$EDITOR_DIR/Helpers/UnityYAMLMerge}"
[ -x "$DRIVER" ] || DRIVER="$EDITOR_DIR/Resources/UnityYAMLMerge"

if [ ! -x "$DRIVER" ]; then
  echo "UnityYAMLMerge not found at: $DRIVER"
  echo "Pass the path as the first argument."
  exit 1
fi

git config merge.tool unityyamlmerge
git config mergetool.unityyamlmerge.trustExitCode false
git config mergetool.unityyamlmerge.cmd "'$DRIVER' merge -p \"\$BASE\" \"\$REMOTE\" \"\$LOCAL\" \"\$MERGED\""
git config merge.unityyamlmerge.name "Unity SmartMerge"
git config merge.unityyamlmerge.driver "'$DRIVER' merge -h -p --force %O %B %A %A"
git config merge.unityyamlmerge.recursive binary
echo "Done. Using $DRIVER"
