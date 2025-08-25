#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
ZIP_FILE="$ROOT_DIR/lambda.zip"

echo "[build] Clean previous artifacts"
rm -rf "$BUILD_DIR" "$ZIP_FILE"

echo "[build] Install dependencies to build directory"
pip install --upgrade pip >/dev/null
pip install -r "$ROOT_DIR/requirements.txt" -t "$BUILD_DIR"

echo "[build] Copy application code"
cp -R "$ROOT_DIR/app" "$BUILD_DIR/"

echo "[build] Create lambda.zip"
(cd "$BUILD_DIR" && zip -r -q "$ZIP_FILE" .)

echo "[build] Done: $ZIP_FILE"
ls -lh "$ZIP_FILE"

