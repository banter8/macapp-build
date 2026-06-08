"""작업 패널 — 우측: 작업 모드 선택, CRF 슬라이더, 진행률, 로그"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..engine.models import ProcessStatus, WorkMode


class TaskPanel(QWidget):
    """우측 작업 패널

    상단: 작업 모드 선택 (Lightning Cut / Master Quality)
    중단: 시간 설정, CRF 슬라이더, 출력 경로
    하단: 진행률 바, NVENC 상태, 로그
    """

    start_requested = Signal()
    cancel_requested = Signal()

    # 모드별 설명
    MODE_DESCRIPTIONS = {
        WorkMode.LIGHTNING_CUT: (
            "⚡ 라이트닝 컷",
            "Stream Copy (-c copy)",
            "화질 손실 0% · 원본 그대로 추출\n"
            "인트로/아웃트로 제거, 단순 길이 조절",
        ),
        WorkMode.MASTER_QUALITY_LOSSLESS: (
            "💎 무손실 (Lossless)",
            "-qp 0 · 수학적 완전 무손실",
            "수학적 완전 무손실 · 고용량\n"
            "크롭/색감 수정 등 편집 후 최종 저장",
        ),
        WorkMode.MASTER_QUALITY_HIGH: (
            "🌟 시각적 무손실 (High Fidelity)",
            "-cq 14~16 · 고효율 압축",
            "인간의 눈으로 판별 불가능한 최적화\n"
            "일상적인 고품질 인코딩에 최적",
        ),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_video: Optional[str] = None
        self._output_path: Optional[str] = None
        self._selected_mode: WorkMode = WorkMode.LIGHTNING_CUT
        self._setup_ui()

    def _setup_ui(self):
        """UI 구성"""
        # 스크롤 가능한 레이아웃
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # ── 제목 ──
        title = QLabel("⚙️ 작업 설정")
        title.setProperty("cssClass", "title")
        layout.addWidget(title)

        # ── 1. 작업 모드 선택 ──
        layout.addWidget(self._build_mode_section())

        # ── 2. 화질 설정 ──
        layout.addWidget(self._build_quality_section())

        # ── 4. 출력 설정 ──
        layout.addWidget(self._build_output_section())

        # ── 5. 시작/취소 버튼 ──
        layout.addWidget(self._build_button_section())

        # ── 6. NVENC 상태 ──
        layout.addWidget(self._build_hw_accel_section())

        # ── 7. 진행률 ──
        layout.addWidget(self._build_progress_section())

        # ── 8. 로그 ──
        layout.addWidget(self._build_log_section())

        layout.addStretch()

        scroll.setWidget(content)

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ──────────────────────────────────────────────
    # 섹션 빌더
    # ──────────────────────────────────────────────

    def _build_mode_section(self) -> QGroupBox:
        """작업 모드 선택 그룹"""
        group = QGroupBox("작업 방식")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.mode_buttons = {}
        for i, (mode, (title, subtitle, desc)) in enumerate(self.MODE_DESCRIPTIONS.items()):
            btn = QRadioButton(f" {title}")
            btn.setProperty("cssClass", "modeBtn")
            btn.setStyleSheet("padding: 8px;")
            btn.setToolTip(f"{subtitle}\n\n{desc}")

            desc_label = QLabel(desc)
            desc_label.setProperty("cssClass", "subtitle")
            desc_label.setWordWrap(True)
            desc_label.setIndent(24)

            self.mode_group.addButton(btn, i)
            self.mode_buttons[mode] = (btn, desc_label)

            layout.addWidget(btn)
            layout.addWidget(desc_label)

        # 기본 선택: Lightning Cut
        self.mode_buttons[WorkMode.LIGHTNING_CUT][0].setChecked(True)
        self.mode_group.idClicked.connect(self._on_mode_changed)

        return group

    def _build_quality_section(self) -> QGroupBox:
        """화질 설정 그룹 (CRF/CQ 슬라이더)"""
        group = QGroupBox("화질 설정 (Master Quality 전용)")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # CQ 슬라이더
        cq_row = QHBoxLayout()
        cq_row.addWidget(QLabel("CQ 레벨:"))

        self.cq_slider = QSlider(Qt.Horizontal)
        self.cq_slider.setRange(14, 16)
        self.cq_slider.setValue(14)
        self.cq_slider.setTickPosition(QSlider.TicksBelow)
        self.cq_slider.setTickInterval(1)
        self.cq_slider.setSingleStep(1)
        self.cq_slider.setPageStep(1)
        self.cq_slider.valueChanged.connect(self._on_cq_changed)
        cq_row.addWidget(self.cq_slider, stretch=1)

        self.cq_value_label = QLabel("14")
        self.cq_value_label.setFixedWidth(30)
        self.cq_value_label.setAlignment(Qt.AlignCenter)
        cq_row.addWidget(self.cq_value_label)

        layout.addLayout(cq_row)

        # CQ 설명
        self.cq_desc_label = QLabel("14: 최고 품질 · 시각적 무손실")
        self.cq_desc_label.setProperty("cssClass", "subtitle")
        self.cq_desc_label.setWordWrap(True)
        layout.addWidget(self.cq_desc_label)

        # 품질 프리셋 힌트
        preset_label = QLabel(
            "14 = 최고 품질 (권장)\n"
            "15 = 높은 품질\n"
            "16 = 균형 (파일 크기 ↓)"
        )
        preset_label.setProperty("cssClass", "subtitle")
        layout.addWidget(preset_label)

        return group

    def _build_output_section(self) -> QGroupBox:
        """출력 설정 그룹"""
        group = QGroupBox("출력 설정")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # 출력 경로
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("저장 위치:"))

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("자동 생성 (입력 파일 기준)")
        self.output_path_edit.setReadOnly(True)
        path_row.addWidget(self.output_path_edit, stretch=1)

        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_output)
        path_row.addWidget(browse_btn)

        layout.addLayout(path_row)

        # 모드별 확장자 정보
        self.ext_label = QLabel("출력 형식: MP4")
        self.ext_label.setProperty("cssClass", "subtitle")
        layout.addWidget(self.ext_label)

        return group

    def _build_button_section(self) -> QWidget:
        """시작/취소 버튼"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        self.start_btn = QPushButton("▶ 시작")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-size: 14px;
                font-weight: 700;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:disabled {
                background-color: #21262d;
                color: #484f58;
            }
        """)
        self.start_btn.clicked.connect(self.start_requested.emit)
        layout.addWidget(self.start_btn, stretch=2)

        self.cancel_btn = QPushButton("✕ 취소")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #da3633;
                color: white;
                font-size: 14px;
                font-weight: 700;
                padding: 10px 16px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #f85149;
            }
            QPushButton:disabled {
                background-color: #21262d;
                color: #484f58;
            }
        """)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_btn, stretch=1)

        return widget

    def _build_hw_accel_section(self) -> QWidget:
        """NVENC 하드웨어 가속 상태 표시"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.hw_accel_icon = QLabel("🖥️")
        self.hw_accel_icon.setStyleSheet("font-size: 20px;")
        layout.addWidget(self.hw_accel_icon)

        self.hw_accel_label = QLabel("NVENC: 대기 중...")
        self.hw_accel_label.setProperty("cssClass", "subtitle")
        layout.addWidget(self.hw_accel_label, stretch=1)

        return widget

    def _build_progress_section(self) -> QWidget:
        """진행률 표시"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 진행률 + 상태
        status_row = QHBoxLayout()
        self.progress_label = QLabel("진행률: 0%")
        status_row.addWidget(self.progress_label)

        self.status_label = QLabel("대기 중")
        self.status_label.setAlignment(Qt.AlignRight)
        self.status_label.setProperty("cssClass", "subtitle")
        status_row.addWidget(self.status_label)

        layout.addLayout(status_row)

        # 프로그레스 바 (직접 스타일)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        return widget

    def _build_log_section(self) -> QWidget:
        """로그 출력"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("📋 로그"))
        clear_log_btn = QPushButton("지우기")
        clear_log_btn.setFixedWidth(60)
        clear_log_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clear_log_btn)
        layout.addLayout(log_header)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(500)
        self.log_output.setStyleSheet("""
            QPlainTextEdit {
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: 11px;
                background-color: #0d1117;
                color: #8b949e;
            }
        """)
        layout.addWidget(self.log_output, stretch=1)

        return widget

    # ──────────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────────

    def _on_mode_changed(self, mode_id: int):
        """모드 변경 처리"""
        mode_map = list(self.MODE_DESCRIPTIONS.keys())
        if mode_id < len(mode_map):
            self._selected_mode = mode_map[mode_id]

            # CQ 슬라이더 활성화 (Master Quality만)
            is_master = self._selected_mode in (
                WorkMode.MASTER_QUALITY_LOSSLESS,
                WorkMode.MASTER_QUALITY_HIGH,
            )
            self._set_quality_section_enabled(is_master)

            # 확장자 업데이트
            ext = ".mkv" if self._selected_mode == WorkMode.MASTER_QUALITY_LOSSLESS else ".mp4"
            self.ext_label.setText(f"출력 형식: {ext}")

            # 설명 갱신
            for mode, (btn, desc) in self.mode_buttons.items():
                visible = mode == self._selected_mode
                desc.setVisible(visible)

    def _on_cq_changed(self, value: int):
        """CQ 슬라이더 변경"""
        self.cq_value_label.setText(str(value))
        descs = {
            14: "14: 최고 품질 · 시각적 무손실 (권장)",
            15: "15: 높은 품질 · 약간의 압축",
            16: "16: 균형 · 파일 크기와 품질 최적화",
        }
        self.cq_desc_label.setText(descs.get(value, f"{value}: 사용자 설정"))

    def _set_quality_section_enabled(self, enabled: bool):
        """화질 섹션 활성/비활성"""
        self.cq_slider.setEnabled(enabled)
        self.cq_value_label.setEnabled(enabled)
        self.cq_desc_label.setEnabled(enabled)

    def _browse_output(self):
        """출력 경로 찾아보기"""
        from PySide6.QtWidgets import QFileDialog

        if self._current_video:
            base = os.path.splitext(os.path.basename(self._current_video))[0]
            ext = ".mkv" if self._selected_mode == WorkMode.MASTER_QUALITY_LOSSLESS else ".mp4"
            default_dir = os.path.dirname(self._current_video)
            default_name = self._generate_edit_path(default_dir, base, ext)
        else:
            default_name = "output.mp4"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "출력 파일 저장",
            default_name,
            "MP4 (*.mp4);;MKV (*.mkv);;모든 파일 (*.*)",
        )
        if path:
            self._output_path = path
            self.output_path_edit.setText(path)

    def _clear_log(self):
        """로그 초기화"""
        self.log_output.clear()

    # ──────────────────────────────────────────────
    # Public API (MainWindow에서 호출)
    # ──────────────────────────────────────────────

    def set_video(self, path: str):
        """비디오 로드 시 호출 — 자동 저장 경로 생성"""
        self._current_video = path
        base = os.path.splitext(os.path.basename(path))[0]
        ext = ".mkv" if self._selected_mode == WorkMode.MASTER_QUALITY_LOSSLESS else ".mp4"
        output_dir = os.path.dirname(path)

        # _edit01, _edit02, ... 중복 방지
        auto_path = self._generate_edit_path(output_dir, base, ext)
        self._output_path = auto_path
        self.output_path_edit.setText(auto_path)
        self.append_log(f"[파일] {os.path.basename(path)} 로드됨")

    @staticmethod
    def _generate_edit_path(directory: str, base_name: str, ext: str) -> str:
        """_edit01, _edit02 ... 순번 자동 생성"""
        for i in range(1, 1000):
            candidate = os.path.join(directory, f"{base_name}_edit{i:02d}{ext}")
            if not os.path.exists(candidate):
                return candidate
        # 999개를 다 채웠으면 강제 덮어쓰기
        return os.path.join(directory, f"{base_name}_edit999{ext}")

    def set_output_path(self, path: str):
        """출력 경로 설정"""
        self._output_path = path
        self.output_path_edit.setText(path)

    def set_running_state(self, is_running: bool):
        """실행 상태 변경"""
        self.start_btn.setEnabled(not is_running)
        self.cancel_btn.setEnabled(is_running)
        if is_running:
            self.start_btn.setText("⏳ 처리 중...")
        else:
            self.start_btn.setText("▶ 시작")

    def update_progress(self, percent: float, status: str = ""):
        """진행률 업데이트"""
        self.progress_bar.setValue(int(percent))
        self.progress_label.setText(f"진행률: {percent:.1f}%")
        if status:
            self.status_label.setText(status)

    def append_log(self, line: str):
        """로그 추가"""
        self.log_output.appendPlainText(line)
        # 자동 스크롤
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def set_hw_accel_indicator(self, enabled: bool):
        """NVENC 가속 상태 표시"""
        if enabled:
            self.hw_accel_icon.setText("✅")
            self.hw_accel_label.setText("NVENC: 활성 (RTX 3090)")
            self.hw_accel_label.setStyleSheet("color: #3fb950; font-weight: 600;")
        else:
            self.hw_accel_icon.setText("⚠️")
            self.hw_accel_label.setText("NVENC: 비활성 (CPU 인코딩)")
            self.hw_accel_label.setStyleSheet("color: #d29922; font-weight: 600;")

    # ── Getter ─────────────────────────

    def get_selected_mode(self) -> WorkMode:
        return self._selected_mode

    def get_cq_value(self) -> int:
        return self.cq_slider.value()

    def get_output_path(self) -> Optional[str]:
        return self._output_path
