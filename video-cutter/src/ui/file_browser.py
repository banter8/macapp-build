"""파일 브라우저 패널 — 좌측: 파일 탐색기 + 최근 작업 목록"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QDir, QModelIndex
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileSystemModel,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ..utils.helpers import format_file_size


class FileBrowserPanel(QWidget):
    """좌측 파일 브라우저 패널

    상단: 파일 시스템 트리 (QTreeView + QFileSystemModel)
    하단: 최근 작업 목록 (QListWidget)
    """

    file_selected = Signal(str)  # 선택된 파일 경로

    # 지원하는 비디오 확장자
    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".mts", ".m2ts"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recent_files: List[str] = []
        self._current_root: str = ""

        self._setup_ui()
        self._setup_file_system()

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── 상단: 파일 시스템 트리 ──
        fs_label = QLabel("📁 파일 탐색기")
        fs_label.setProperty("cssClass", "title")
        layout.addWidget(fs_label)

        self.tree_view = QTreeView()
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(16)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.doubleClicked.connect(self._on_tree_double_click)
        layout.addWidget(self.tree_view, stretch=3)

        # ── 하단: 최근 파일 ──
        recent_label = QLabel("🕐 최근 작업")
        recent_label.setProperty("cssClass", "title")
        layout.addWidget(recent_label)

        self.recent_list = QListView()
        self.recent_list.setAlternatingRowColors(True)
        self.recent_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.recent_list.doubleClicked.connect(self._on_recent_double_click)
        layout.addWidget(self.recent_list, stretch=2)

        # ── 비우기 버튼 ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        clear_btn = QPushButton("비우기")
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self._clear_recent)
        btn_layout.addWidget(clear_btn)
        layout.addLayout(btn_layout)

    def _setup_file_system(self):
        """파일 시스템 모델 설정"""
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(QDir.rootPath())
        self.fs_model.setNameFilterDisables(False)

        # 비디오 파일만 필터 (선택적 — 주석 해제 시 비디오만 표시)
        # self.fs_model.setNameFilters(["*.mp4", "*.mkv", "*.avi", "*.mov"])

        self.tree_view.setModel(self.fs_model)

        # 기본 경로: 내 문서 / 비디오
        home = Path.home()
        default_paths = [
            home / "Videos",
            home / "Downloads",
            home / "Desktop",
            home / "Documents",
        ]
        for dp in default_paths:
            if dp.exists():
                root = str(dp)
                break
        else:
            root = str(home)

        self._set_root(root)

        # 헤더 설정
        header = self.tree_view.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 이름 stretch
        for i in range(1, header.count()):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            header.hideSection(i)  # 이름만 표시

    def _set_root(self, path: str):
        """트리 루트 설정"""
        self._current_root = path
        root_index = self.fs_model.setRootPath(path)
        self.tree_view.setRootIndex(root_index)

    # ──────────────────────────────────────────────
    # 파일 선택
    # ──────────────────────────────────────────────

    def _on_tree_double_click(self, index: QModelIndex):
        """트리 더블클릭 → 파일 열기"""
        path = self.fs_model.filePath(index)
        if os.path.isfile(path) and self._is_video_file(path):
            self.file_selected.emit(path)

    def _on_recent_double_click(self, index):
        """최근 목록 더블클릭 → 파일 열기"""
        row = index.row()
        if 0 <= row < len(self._recent_files):
            path = self._recent_files[row]
            if os.path.exists(path):
                self.file_selected.emit(path)

    # ──────────────────────────────────────────────
    # 최근 파일 관리
    # ──────────────────────────────────────────────

    def add_recent(self, path: str):
        """최근 파일 목록에 추가"""
        if not path:
            return

        # 중복 제거
        if path in self._recent_files:
            self._recent_files.remove(path)

        # 앞에 추가 (최대 20개)
        self._recent_files.insert(0, path)
        if len(self._recent_files) > 20:
            self._recent_files = self._recent_files[:20]

        self._update_recent_ui()

    def _update_recent_ui(self):
        """최근 파일 목록 UI 업데이트"""
        model = QStandardItemModel()
        for path in self._recent_files:
            filename = os.path.basename(path)
            dirname = os.path.dirname(path)

            item = QStandardItem(f"🎬 {filename}")
            item.setToolTip(f"{path}\n{dirname}")
            item.setData(path, Qt.UserRole)
            model.appendRow(item)

        self.recent_list.setModel(model)

    def _clear_recent(self):
        """최근 파일 목록 비우기"""
        self._recent_files.clear()
        self._update_recent_ui()

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    @staticmethod
    def _is_video_file(path: str) -> bool:
        """비디오 파일인지 확인"""
        ext = os.path.splitext(path)[1].lower()
        return ext in FileBrowserPanel.VIDEO_EXTENSIONS
