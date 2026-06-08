"""메인 윈도우 — 3분할 레이아웃 (파일 / 뷰어 / 작업 패널)"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..engine.models import CropRegion, JobConfig, ProcessStatus, WorkMode, VideoInfo
from ..engine.process_manager import ProcessManager
from .file_browser import FileBrowserPanel
from .task_panel import TaskPanel
from .video_viewer import VideoViewer


class MainWindow(QMainWindow):
    """Video Cutter Pro 메인 윈도우"""

    APP_NAME = "Video Cutter Pro"
    APP_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.APP_NAME} v{self.APP_VERSION}")
        self.setMinimumSize(1280, 720)
        self.resize(1600, 900)

        # ── 상태 ─────────────────────────
        self._current_video: Optional[str] = None
        self._video_info: Optional[VideoInfo] = None
        self._process_manager = ProcessManager()

        # ── UI 구성 ──────────────────────
        self._setup_menu()
        self._setup_central()
        self._setup_statusbar()
        self._setup_signals()
        self.setAcceptDrops(True)  # 드래그앤드랍 활성화

    # ──────────────────────────────────────────────
    # UI 셋업
    # ──────────────────────────────────────────────

    def _setup_menu(self):
        """메뉴바 구성"""
        menubar = self.menuBar()

        # 파일 메뉴
        file_menu = menubar.addMenu("파일(&F)")
        open_action = QAction("열기(&O)...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)

        export_action = QAction("내보내기(&E)...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._on_save_as)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("종료(&X)", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 작업 메뉴
        job_menu = menubar.addMenu("작업(&J)")
        start_action = QAction("시작(&S)", self)
        start_action.setShortcut(QKeySequence("Ctrl+R"))
        start_action.triggered.connect(self._on_start_job)
        job_menu.addAction(start_action)

        cancel_action = QAction("취소(&C)", self)
        cancel_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        cancel_action.triggered.connect(self._on_cancel_job)
        job_menu.addAction(cancel_action)

        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말(&H)")
        about_action = QAction("정보(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_central(self):
        """중앙 3분할 위젯"""
        # ── 좌측: 파일 브라우저 ──
        self.file_browser = FileBrowserPanel()
        self.file_browser.file_selected.connect(self._on_file_selected)

        # ── 중앙: 비디오 뷰어 ──
        self.video_viewer = VideoViewer()

        # ── 우측: 작업 패널 ──
        self.task_panel = TaskPanel()
        self.task_panel.start_requested.connect(self._on_start_job)
        self.task_panel.cancel_requested.connect(self._on_cancel_job)

        # ── 스플리터 ──
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.file_browser)
        self.splitter.addWidget(self.video_viewer)
        self.splitter.addWidget(self.task_panel)

        # 비율: 파일 1 : 뷰어 3 : 패널 1.2
        self.splitter.setSizes([250, 750, 300])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setStretchFactor(2, 1)

        self.setCentralWidget(self.splitter)

    def _setup_statusbar(self):
        """상태 표시줄"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = self.status_bar.currentMessage()
        self.status_bar.showMessage(f"{self.APP_NAME} v{self.APP_VERSION} | 대기 중...")

    def _setup_signals(self):
        """ProcessManager 시그널 연결"""
        self._process_manager.connect_signals(
            on_progress=self._on_progress,
            on_log=self._on_log_line,
            on_finished=self._on_job_finished,
            on_hw_accel=self._on_hw_accel_status,
        )

    # ──────────────────────────────────────────────
    # 파일 작업
    # ──────────────────────────────────────────────

    def _on_open_file(self):
        """파일 열기 다이얼로그"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "비디오 파일 열기",
            "",
            "비디오 파일 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v);;모든 파일 (*.*)",
        )
        if file_path:
            self._load_video(file_path)

    def _on_save_as(self):
        """다른 이름으로 저장 다이얼로그"""
        if not self._current_video:
            QMessageBox.warning(self, "알림", "먼저 비디오 파일을 열어주세요.")
            return

        default_name = f"output_{os.path.basename(self._current_video)}"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "출력 파일 저장",
            default_name,
            "MP4 파일 (*.mp4);;MKV 파일 (*.mkv);;모든 파일 (*.*)",
        )
        if file_path:
            self.task_panel.set_output_path(file_path)

    def _load_video(self, path: str):
        """비디오 로드"""
        if not os.path.exists(path):
            QMessageBox.critical(self, "오류", f"파일을 찾을 수 없습니다:\n{path}")
            return

        self._current_video = path
        filename = os.path.basename(path)

        # VideoInfo 생성 (실제 분석은 ffprobe로, 여기서는 기본 정보)
        self._video_info = VideoInfo(path=path)

        # UI 업데이트
        self.video_viewer.load_video(path)
        self.file_browser.add_recent(path)
        self.task_panel.set_video(path)
        self.status_bar.showMessage(f"로드됨: {filename}")

        self.setWindowTitle(f"{self.APP_NAME} - {filename}")

    def _on_file_selected(self, path: str):
        """파일 브라우저에서 파일 선택"""
        self._load_video(path)

    # ──────────────────────────────────────────────
    # 작업 실행
    # ──────────────────────────────────────────────

    def _on_start_job(self):
        """인코딩 작업 시작"""
        if not self._current_video:
            QMessageBox.warning(self, "알림", "먼저 비디오 파일을 열어주세요.")
            return

        if self._process_manager.is_running:
            QMessageBox.warning(self, "알림", "이미 작업이 실행 중입니다.")
            return

        # 작업 설정 수집
        config = self._collect_job_config()
        if not config:
            return

        # 작업 시작
        self.task_panel.set_running_state(True)
        self.status_bar.showMessage("작업 실행 중...")
        self._process_manager.start(config)

    def _on_cancel_job(self):
        """작업 취소"""
        if self._process_manager.is_running:
            self._process_manager.cancel()
            self.status_bar.showMessage("작업 취소 중...")

    def _collect_job_config(self) -> Optional[JobConfig]:
        """UI 상태 → JobConfig"""
        config = JobConfig()
        config.input_path = self._current_video or ""

        # 모드
        mode = self.task_panel.get_selected_mode()
        config.mode = mode

        # 크롭
        crop = self.video_viewer.get_crop_region()
        if crop and crop.is_valid():
            config.crop = crop

        # 시간 범위 (VideoViewer 타임슬라이더)
        in_sec, out_sec = self.video_viewer.get_time_range()
        if in_sec > 0:
            config.start_time = self._sec_to_time_str(in_sec)
        if out_sec > 0:
            config.end_time = self._sec_to_time_str(out_sec)

        # CRF / CQ 값
        config.cq_level = self.task_panel.get_cq_value()

        # 출력 경로 — 항상 새로 생성 (덮어쓰기 방지)
        base = os.path.splitext(os.path.basename(self._current_video or ""))[0]
        ext = ".mkv" if mode == WorkMode.MASTER_QUALITY_LOSSLESS else ".mp4"
        output_dir = os.path.dirname(self._current_video or ".")
        config.output_path = self.task_panel._generate_edit_path(output_dir, base, ext)

        return config

    # ──────────────────────────────────────────────
    # 시그널 핸들러
    # ──────────────────────────────────────────────

    def _on_progress(self, percent: float, status: str):
        """진행률 업데이트"""
        self.task_panel.update_progress(percent, status)
        self.status_bar.showMessage(f"인코딩 중... {percent:.1f}%")

    def _on_log_line(self, line: str):
        """로그 라인"""
        self.task_panel.append_log(line)

    def _on_job_finished(self, success: bool, message: str):
        """작업 완료"""
        self.task_panel.set_running_state(False)

        if success:
            self.task_panel.update_progress(100.0, "✅ 완료!")
            self.status_bar.showMessage("✅ 작업 완료!")
            # 완료 알림
            output_path = self.task_panel.get_output_path()
            if output_path and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                size_mb = file_size / (1024 * 1024)
                msg = f"출력 파일: {os.path.basename(output_path)}\n크기: {size_mb:.1f} MB"
                QMessageBox.information(self, "작업 완료", msg)
        else:
            self.task_panel.append_log(f"\n[오류] {message}")
            self.status_bar.showMessage(f"❌ 작업 실패")
            QMessageBox.critical(self, "작업 실패", message)

    def _on_hw_accel_status(self, enabled: bool):
        """NVENC 상태 업데이트"""
        self.task_panel.set_hw_accel_indicator(enabled)

    @staticmethod
    def _sec_to_time_str(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ──────────────────────────────────────────────
    # 드래그앤드랍
    # ──────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        """드래그 진입 — 비디오 파일만 허용"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if self._is_video_file(url.toLocalFile()):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent):
        """드롭 — 파일 로드"""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if self._is_video_file(path):
                self._load_video(path)
                break

    @staticmethod
    def _is_video_file(path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        return ext in {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts", ".m2ts"}

    # ──────────────────────────────────────────────
    # 기타
    # ──────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self,
            f"{self.APP_NAME} v{self.APP_VERSION}",
            f"""<h2>{self.APP_NAME}</h2>
            <p>버전: {self.APP_VERSION}</p>
            <p>PySide6 기반 FFmpeg GUI 프론트엔드</p>
            <hr>
            <p><b>라이트닝 컷:</b> Stream Copy, 화질 손실 0%</p>
            <p><b>마스터 퀄리티:</b> NVENC 하드웨어 가속 인코딩</p>
            <hr>
            <p>Windows 10/11 전용 | FFmpeg 필요</p>""",
        )

    def closeEvent(self, event):
        """종료 시 실행 중인 작업 확인"""
        if self._process_manager.is_running:
            reply = QMessageBox.question(
                self,
                "작업 중",
                "현재 인코딩 작업이 실행 중입니다.\n정말 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._process_manager.cancel()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
