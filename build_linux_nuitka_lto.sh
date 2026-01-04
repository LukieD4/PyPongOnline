#!/usr/bin/env bash
set -euo pipefail

# Build script for Nuitka onefile
# Place this file in /home/lukie/Desktop/aaaaa/PyPongOnline and run ./build.sh

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENTRY_POINT="py_client.py"
OUT_DIR="${PROJECT_DIR}/build_linux"
OUT_NAME="pypongonline"

# Data directories to include (source=target)
INCLUDE_AUDIO="${PROJECT_DIR}/audio=audio"
INCLUDE_SPRITES="${PROJECT_DIR}/sprites=sprites"
INCLUDE_STAGES="${PROJECT_DIR}/stages=stages"

# Modules to force-include even if not detected as imports
FORCE_MODULES=(
  "py_input"
  "py_config"
  "py_render"
  "py_soundmixer"
  "py_sprites"
  "py_stager"
  "py_ui_sprites"
  "py_resource"
  "websockets"
  "websockets.client"
  "websockets.asyncio"
  "websockets.asyncio.client"
)


# Allow user to override number of parallel jobs via JOBS env var
: "${JOBS:=$(nproc)}"

# Find python executable: prefer activated venv, then common venv folders, then system python3
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
elif [[ -x "${PROJECT_DIR}/venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_DIR}/venv/bin/python"
elif [[ -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
elif [[ -x "${PROJECT_DIR}/project/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_DIR}/project/bin/python"
else
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

echo "Using Python: ${PYTHON_BIN}"
echo "Project dir: ${PROJECT_DIR}"
echo "Output dir: ${OUT_DIR}"
echo "Parallel jobs: ${JOBS}"

# Ensure Nuitka is installed in the chosen Python environment
if ! "${PYTHON_BIN}" -c "import nuitka" >/dev/null 2>&1; then
  echo "Nuitka is not installed in the selected Python environment."
  echo "Install it with: ${PYTHON_BIN} -m pip install nuitka"
  exit 1
fi

# Create output dir
mkdir -p "${OUT_DIR}"

# Base build command
BUILD_CMD=(
  "${PYTHON_BIN}" -m nuitka
  --standalone
  --onefile
  --remove-output
  --output-dir="${OUT_DIR}"
  --include-data-dir="${INCLUDE_AUDIO}"
  --include-data-dir="${INCLUDE_SPRITES}"
  --include-data-dir="${INCLUDE_STAGES}"
  --follow-imports
  --show-progress
  --assume-yes-for-downloads
  --output-filename="${OUT_NAME}"
  --lto="yes"
  --jobs="${JOBS}"
  "${PROJECT_DIR}/${ENTRY_POINT}"
)

# Append --include-module flags for each forced module
for m in "${FORCE_MODULES[@]}"; do
  BUILD_CMD+=( "--include-module=${m}" )
done

echo "Running Nuitka build with forced modules: ${FORCE_MODULES[*]}"
printf '%q ' "${BUILD_CMD[@]}"
echo
"${BUILD_CMD[@]}"

echo
echo "Build finished. Executable (onefile) will be in ${OUT_DIR}."
echo "- The build used LTO and ${JOBS} parallel jobs; linking may take longer but produces optimized output."
echo "- If you run out of memory during parallel compilation, reduce JOBS (for example JOBS=8 ./build.sh)."
echo "- Test the produced executable on a clean machine to verify all libraries and assets are bundled."
