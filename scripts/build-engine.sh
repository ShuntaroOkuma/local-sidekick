#!/bin/bash
# Build script: bundle standalone Python + engine for Electron app packaging.
#
# Supports macOS (arm64/x64), Linux (x64), and Windows (x64, via Git Bash on CI).
#
# Usage:
#   bash scripts/build-engine.sh
#
# Output:
#   client/build-engine/python/   - Standalone Python 3.12 with all dependencies
#   client/build-engine/engine/   - Engine source + seed model files

set -euo pipefail

# --- Configuration ---
PYTHON_VERSION="3.12.12"
STANDALONE_TAG="20260211"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENT_DIR="${PROJECT_ROOT}/client"
BUILD_DIR="${CLIENT_DIR}/build-engine"
ENGINE_SRC="${PROJECT_ROOT}/engine"
CACHE_DIR="${PROJECT_ROOT}/.cache"

# --- Detect OS and architecture ---
OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
  Darwin)
    case "$ARCH" in
      arm64)  PBS_TRIPLE="aarch64-apple-darwin" ;;
      x86_64) PBS_TRIPLE="x86_64-apple-darwin"  ;;
      *)      echo "Error: Unsupported macOS architecture: $ARCH" >&2; exit 1 ;;
    esac
    PIP_EXTRAS="all"
    PYTHON_BIN_REL="python/bin/python3"
    SITE_PKG_REL="python/lib/python3.12/site-packages"
    ;;
  Linux)
    PBS_TRIPLE="x86_64-unknown-linux-gnu"
    PIP_EXTRAS="camera,llama,download"
    PYTHON_BIN_REL="python/bin/python3"
    SITE_PKG_REL="python/lib/python3.12/site-packages"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    PBS_TRIPLE="x86_64-pc-windows-msvc"
    PIP_EXTRAS="camera,llama,download"
    PYTHON_BIN_REL="python/python.exe"
    SITE_PKG_REL="python/Lib/site-packages"
    ;;
  *)
    echo "Error: Unsupported OS: $OS" >&2; exit 1 ;;
esac

echo "=== Building engine for ${OS} ${ARCH} ==="
echo "Python: ${PYTHON_VERSION}+${STANDALONE_TAG}"
echo "Triple: ${PBS_TRIPLE}"
echo "Extras: ${PIP_EXTRAS}"
echo ""

# --- Step 1: Clean previous build ---
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
mkdir -p "${CACHE_DIR}"

# --- Step 2: Download python-build-standalone ---
TARBALL="cpython-${PYTHON_VERSION}+${STANDALONE_TAG}-${PBS_TRIPLE}-install_only_stripped.tar.gz"
DOWNLOAD_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${STANDALONE_TAG}/${TARBALL}"

if [ -f "${CACHE_DIR}/${TARBALL}" ]; then
  echo "[1/5] Using cached Python (${TARBALL})"
else
  echo "[1/5] Downloading standalone Python..."
  curl -L --progress-bar -o "${CACHE_DIR}/${TARBALL}" "${DOWNLOAD_URL}"
fi

# --- Step 3: Extract standalone Python ---
echo "[2/5] Extracting standalone Python..."
tar xzf "${CACHE_DIR}/${TARBALL}" -C "${BUILD_DIR}"

PYTHON_BIN="${BUILD_DIR}/${PYTHON_BIN_REL}"

if [ ! -f "${PYTHON_BIN}" ]; then
  echo "Error: Python binary not found at ${PYTHON_BIN}" >&2
  exit 1
fi

echo "  Python: $("${PYTHON_BIN}" --version)"

# --- Step 4: Install engine dependencies ---
echo "[3/5] Installing engine dependencies..."
"${PYTHON_BIN}" -m pip install --no-cache-dir --quiet --upgrade pip
"${PYTHON_BIN}" -m pip install --no-cache-dir --quiet "${ENGINE_SRC}[${PIP_EXTRAS}]"

# --- Step 5: Copy engine source + seed models ---
echo "[4/5] Copying engine source and seed models..."
mkdir -p "${BUILD_DIR}/engine/engine"
cp -r "${ENGINE_SRC}/engine/"* "${BUILD_DIR}/engine/engine/"
cp "${ENGINE_SRC}/pyproject.toml" "${BUILD_DIR}/engine/"

# Copy face_landmarker.task as seed model (small, needed for camera)
mkdir -p "${BUILD_DIR}/engine/models"
if [ -f "${ENGINE_SRC}/models/face_landmarker.task" ]; then
  cp "${ENGINE_SRC}/models/face_landmarker.task" "${BUILD_DIR}/engine/models/"
  echo "  Bundled: face_landmarker.task"
else
  echo "  Warning: face_landmarker.task not found (will be downloaded on first launch)"
fi
# Do NOT copy *.gguf files (2-5GB each, downloaded on demand via UI)

# --- Step 6: Strip unnecessary files ---
echo "[5/5] Stripping unnecessary files to reduce size..."

SITE_PACKAGES="${BUILD_DIR}/${SITE_PKG_REL}"

# Remove __pycache__ and .pyc files
find "${BUILD_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -name "*.pyc" -delete 2>/dev/null || true
find "${BUILD_DIR}" -name "*.pyo" -delete 2>/dev/null || true

# Remove test suites from site-packages
find "${SITE_PACKAGES}" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "${SITE_PACKAGES}" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true

# Remove pip, setuptools, wheel (not needed at runtime)
rm -rf "${SITE_PACKAGES}/pip" "${SITE_PACKAGES}/pip-"*.dist-info
rm -rf "${SITE_PACKAGES}/setuptools" "${SITE_PACKAGES}/setuptools-"*.dist-info
rm -rf "${SITE_PACKAGES}/wheel" "${SITE_PACKAGES}/wheel-"*.dist-info
rm -rf "${SITE_PACKAGES}/_distutils_hack"

# Remove stdlib modules not needed at runtime (path differs on Windows)
case "$OS" in
  MINGW*|MSYS*|CYGWIN*)
    rm -rf "${BUILD_DIR}/python/Lib/test"
    rm -rf "${BUILD_DIR}/python/Lib/idlelib"
    rm -rf "${BUILD_DIR}/python/Lib/tkinter"
    rm -rf "${BUILD_DIR}/python/Lib/ensurepip"
    rm -rf "${BUILD_DIR}/python/Lib/turtledemo"
    ;;
  *)
    rm -rf "${BUILD_DIR}/python/lib/python3.12/test"
    rm -rf "${BUILD_DIR}/python/lib/python3.12/idlelib"
    rm -rf "${BUILD_DIR}/python/lib/python3.12/tkinter"
    rm -rf "${BUILD_DIR}/python/lib/python3.12/lib-tk"
    rm -rf "${BUILD_DIR}/python/lib/python3.12/ensurepip"
    rm -rf "${BUILD_DIR}/python/lib/python3.12/turtledemo"
    ;;
esac

# --- Report ---
echo ""
echo "=== Build complete ==="
echo "  Python:  $(du -sh "${BUILD_DIR}/python" | cut -f1)"
echo "  Engine:  $(du -sh "${BUILD_DIR}/engine" | cut -f1)"
echo "  Total:   $(du -sh "${BUILD_DIR}" | cut -f1)"
echo ""
echo "Next: cd client && npm run build:package"
