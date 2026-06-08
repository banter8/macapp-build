#!/usr/bin/env python3
"""Video Cutter Pro — 진입점

사용법:
    python main.py

환경:
    - Python 3.9+
    - PySide6 (pip install PySide6)
    - FFmpeg (ffmpeg/ffmpeg.exe 또는 PATH)
"""

from __future__ import annotations

import sys
import os

# 프로젝트 루트를 sys.path에 추가
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)


def main():
    """메인 함수"""
    # FFmpeg 체크
    ffmpeg_internal = os.path.join(_current_dir, "ffmpeg", "ffmpeg.exe")
    if not os.path.exists(ffmpeg_internal):
        # 시스템 ffmpeg 체크는 런타임에
        print("[정보] 내장 FFmpeg 없음 — 시스템 PATH의 ffmpeg 사용")
        print("       ffmpeg/ffmpeg.exe를 프로그램 폴더에 넣으세요.")

    from src.app import VideoCutterApp

    app = VideoCutterApp()
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
