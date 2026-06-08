"""애플리케이션 부트스트랩 — QApplication 생성 및 실행"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSysInfo
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from . import __app_name__, __version__
from .ui.main_window import MainWindow
from .ui.theme import load_stylesheet


class VideoCutterApp:
    """애플리케이션 셋업 클래스"""

    def __init__(self, argv: list = None):
        if argv is None:
            argv = sys.argv

        self.app = QApplication(argv)
        self._setup_application()
        self._setup_font()

        # 스타일시트 로드
        qss_path = self._get_qss_path()
        load_stylesheet(self.app, qss_path)

        # 메인 윈도우
        self.window = MainWindow()
        self.window.show()

    def _setup_application(self):
        """QApplication 기본 설정"""
        self.app.setApplicationName(__app_name__)
        self.app.setApplicationVersion(__version__)
        self.app.setOrganizationName("VideoCutterPro")

        # Windows 10/11에 최적화된 스타일
        if QSysInfo.productType() == "windows":
            # Windows 11에서 네이티브 스타일 사용
            self.app.setStyle("Fusion")

    def _setup_font(self):
        """기본 폰트 설정"""
        font = QFont("Segoe UI", 10)
        font.setStyleStrategy(QFont.PreferAntialias)
        self.app.setFont(font)

    def _get_qss_path(self) -> str:
        """QSS 파일 경로"""
        # 패키징 시 _MEIPASS (PyInstaller)
        if hasattr(sys, "_MEIPASS"):
            base = Path(sys._MEIPASS)
        else:
            base = Path(__file__).parent.parent

        return str(base / "resources" / "styles" / "dark_theme.qss")

    def run(self) -> int:
        """애플리케이션 실행"""
        return self.app.exec()
