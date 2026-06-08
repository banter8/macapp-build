"""유틸리티 함수 모음"""
from __future__ import annotations

import os
import sys
import re
from typing import Optional


# ──────────────────────────────────────────────
# 파일 크기 포맷
# ──────────────────────────────────────────────

def format_file_size(size_bytes: int) -> str:
    """파일 크기를 사람이 읽기 쉬운 형식으로 변환"""
    if size_bytes <= 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    size = float(size_bytes)

    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1

    return f"{size:.1f} {units[unit_idx]}"


# ──────────────────────────────────────────────
# 시간 변환
# ──────────────────────────────────────────────

_TIME_RE = re.compile(r"^(\d+):(\d+):(\d+)(?:\.(\d+))?$")


def parse_time_to_sec(time_str: Optional[str]) -> float:
    """HH:MM:SS[.ms] → 초 (float)"""
    if not time_str:
        return 0.0

    m = _TIME_RE.match(time_str.strip())
    if not m:
        return 0.0

    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ms = int(m.group(4)) if m.group(4) else 0
    return h * 3600 + mi * 60 + s + ms / 100.0


def format_time(seconds: float) -> str:
    """초 → HH:MM:SS 형식"""
    if seconds < 0:
        return "--:--:--"

    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ──────────────────────────────────────────────
# FFmpeg 경로 찾기
# ──────────────────────────────────────────────

def _ffmpeg_bin_name() -> str:
    """플랫폼별 FFmpeg 실행 파일명"""
    return "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def find_ffmpeg_path() -> str:
    """FFmpeg 실행 파일 경로 찾기

    Windows: ffmpeg.exe / macOS/Linux: ffmpeg
    우선순위:
    1. PyInstaller _internal에 번들된 ffmpeg
    2. 앱과 같은 폴더의 ffmpeg/
    3. 프로젝트 루트 ffmpeg/
    4. 시스템 PATH
    """
    bin_name = _ffmpeg_bin_name()

    # 1. PyInstaller _internal에 번들
    if hasattr(sys, "_MEIPASS"):
        internal = os.path.join(sys._MEIPASS, "ffmpeg", bin_name)
        if os.path.exists(internal):
            return internal

    # 2. PyInstaller — 앱과 같은 폴더
    if hasattr(sys, "frozen"):
        bundle_dir = os.path.dirname(sys.executable)
        internal = os.path.join(bundle_dir, "ffmpeg", bin_name)
        if os.path.exists(internal):
            return internal

    # 3. 개발 환경 — 프로젝트 루트
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for name in (bin_name, "ffmpeg"):
        p = os.path.join(base, "ffmpeg", name)
        if os.path.exists(p):
            return p

    # 4. 시스템 PATH
    return "ffmpeg"
