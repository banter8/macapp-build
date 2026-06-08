"""다크 테마 로더 — QSS 파일을 읽어 QApplication에 적용"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


def load_stylesheet(app: QApplication, qss_path: Optional[str] = None) -> bool:
    """QSS 스타일시트 로드 및 적용

    Args:
        app: QApplication 인스턴스
        qss_path: QSS 파일 경로 (기본값: resources/styles/dark_theme.qss)

    Returns:
        로드 성공 여부
    """
    if qss_path is None:
        # 프로젝트 루트 기준 상대 경로
        base = Path(__file__).parent.parent.parent
        qss_path = str(base / "resources" / "styles" / "dark_theme.qss")

    if not os.path.exists(qss_path):
        print(f"[경고] QSS 파일 없음: {qss_path}")
        _apply_fallback_palette(app)
        return False

    with open(qss_path, "r", encoding="utf-8") as f:
        stylesheet = f.read()

    app.setStyleSheet(stylesheet)
    return True


def _apply_fallback_palette(app: QApplication):
    """QSS 없을 때 QPalette으로 기본 다크 테마 적용"""
    palette = QPalette()

    # 배경
    palette.setColor(QPalette.Window, QColor("#1a1b1e"))
    palette.setColor(QPalette.WindowText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Base, QColor("#16181c"))
    palette.setColor(QPalette.AlternateBase, QColor("#1c1f26"))
    palette.setColor(QPalette.ToolTipBase, QColor("#21262d"))
    palette.setColor(QPalette.ToolTipText, QColor("#c9d1d9"))

    # 텍스트
    palette.setColor(QPalette.Text, QColor("#c9d1d9"))
    palette.setColor(QPalette.Button, QColor("#21262d"))
    palette.setColor(QPalette.ButtonText, QColor("#c9d1d9"))
    palette.setColor(QPalette.BrightText, QColor("#ffffff"))

    # 링크
    palette.setColor(QPalette.Link, QColor("#58a6ff"))
    palette.setColor(QPalette.Highlight, QColor("#1f6feb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))

    # 비활성
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#484f58"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#484f58"))

    app.setPalette(palette)
