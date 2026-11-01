#!/usr/bin/env bash
# Builds the full hobbit house with Blender (macOS/Linux), then opens it.
set -e
cd "$(dirname "$0")"
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
"$BLENDER" --background --python blender/build_scene.py -- --blend hobbit_house.blend
"$BLENDER" hobbit_house.blend &
