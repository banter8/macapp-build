#!/bin/bash
# ══════════════════════════════════════════════════════════════
# Video Cutter Pro — macOS ARM64 (Apple Silicon) 빌드 스크립트
# ══════════════════════════════════════════════════════════════
# 사용법: chmod +x build_mac.sh && ./build_mac.sh
# 요구사항: macOS 14+ (Sonoma), Apple Silicon (M1/M2/M3/M4)
# ══════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo " Video Cutter Pro — macOS 빌드"
echo "============================================"
echo ""

# ── 1. Python 확인 ──────────────────────────────
echo "[1/5] Python 확인..."
if ! command -v python3 &>/dev/null; then
    echo "✗ Python3 필요. https://www.python.org/downloads/"
    exit 1
fi
PYTHON=$(command -v python3)
echo "  Python: $($PYTHON --version)"

# ARM64 확인
ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo "⚠ 경고: Apple Silicon(arm64)이 아닙니다. (현재: $ARCH)"
    echo "  Intel Mac에서도 실행은 가능하나 최적 성능을 위해 M1+ 권장."
fi

# ── 2. 의존성 설치 ──────────────────────────────
echo "[2/5] 의존성 설치..."
$PYTHON -m pip install --upgrade pip --quiet
$PYTHON -m pip install PySide6 pyinstaller --quiet
echo "  PySide6: $($PYTHON -c 'import PySide6; print(PySide6.__version__)')"
echo "  PyInstaller: $($PYTHON -c 'import PyInstaller; print(PyInstaller.__version__)')"

# ── 3. FFmpeg 다운로드 (ARM64 정적 빌드) ──────
echo "[3/5] FFmpeg 다운로드..."
FFMPEG_DIR="ffmpeg"
FFMPEG_BIN="$FFMPEG_DIR/ffmpeg"
FFMPEG_URL="https://evermeet.cx/ffmpeg/ffmpeg/8.1.1/ffmpeg.zip"

if [ -f "$FFMPEG_BIN" ]; then
    echo "  FFmpeg 이미 존재: $(file $FFMPEG_BIN)"
else
    mkdir -p "$FFMPEG_DIR"
    echo "  다운로드 중: $FFMPEG_URL"
    curl -L -o /tmp/ffmpeg.zip "$FFMPEG_URL"
    unzip -o /tmp/ffmpeg.zip -d "$FFMPEG_DIR" > /dev/null 2>&1
    chmod +x "$FFMPEG_BIN"
    rm -f /tmp/ffmpeg.zip
    echo "  FFmpeg 다운로드 완료: $(file $FFMPEG_BIN)"
fi

# ── 4. PyInstaller 빌드 ─────────────────────────
echo "[4/5] PyInstaller 패키징..."
DIST_DIR="dist_mac"
rm -rf "$DIST_DIR" build_mac

$PYTHON -m PyInstaller --clean --onefile --windowed \
    --name "VideoCutterPro" \
    --distpath "$DIST_DIR" \
    --workpath "build_mac" \
    --add-data "resources:resources" \
    --add-binary "$FFMPEG_BIN:ffmpeg" \
    --hidden-import PySide6 \
    --hidden-import PySide6.QtCore \
    --hidden-import PySide6.QtGui \
    --hidden-import PySide6.QtWidgets \
    --hidden-import PySide6.QtMultimedia \
    --hidden-import PySide6.QtMultimediaWidgets \
    main.py

echo "  빌드 완료: $DIST_DIR/VideoCutterPro"

# ── 5. .app 번들 생성 ──────────────────────────
echo "[5/5] .app 번들 생성..."
APP_BUNDLE="$DIST_DIR/VideoCutterPro.app"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

mv "$DIST_DIR/VideoCutterPro" "$APP_BUNDLE/Contents/MacOS/"

# Info.plist 생성
cat > "$APP_BUNDLE/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>VideoCutterPro</string>
    <key>CFBundleIdentifier</key>
    <string>com.videocutterpro.app</string>
    <key>CFBundleName</key>
    <string>Video Cutter Pro</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSArchitecturePriority</key>
    <array>
        <string>arm64</string>
    </array>
</dict>
</plist>
EOF

chmod +x "$APP_BUNDLE/Contents/MacOS/VideoCutterPro"
rm -rf "build_mac"

echo ""
echo "============================================"
echo " ✅ 빌드 완료!"
echo "============================================"
echo ""
echo "  앱 번들: $APP_BUNDLE"
echo "  실행: open $APP_BUNDLE"
echo ""
echo "  (ffmpeg/ 폴더는 빌드 후 삭제해도 됩니다)"
echo "============================================"
