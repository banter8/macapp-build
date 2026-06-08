"""비디오 뷰어 — QVideoSink 프레임 렌더링 + 크롭(동일위젯) + 타임슬라이더"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRect, QSize, Signal, QPoint, QUrl, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QFont, QImage, QKeyEvent, QPainter, QPen, QPixmap,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ..engine.models import CropRegion
from ..utils.helpers import format_time


# ═══════════════════════════════════════════════
# VideoCanvas — 프레임 표시 + 크롭 오버레이 (하나의 위젯)
# ═══════════════════════════════════════════════

class VideoCanvas(QWidget):
    """비디오 프레임 표시 + 크롭 사각형 직접 페인팅"""

    crop_changed = Signal(CropRegion)

    OVERLAY = QColor(0, 0, 0, 100)
    BORDER = QColor("#58a6ff")
    HANDLE = QColor("#1f6feb")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: #000000;")
        self.setMinimumSize(320, 180)

        self._pixmap: Optional[QPixmap] = None
        self._render_rect: QRect = QRect()       # 비디오가 그려지는 실제 영역
        self._video_native: QSize = QSize()       # 원본 해상도

        self._crop_origin: Optional[QPoint] = None
        self._crop_rect: Optional[QRect] = None

    # ── 프레임 업데이트 ──

    def set_frame(self, image: QImage):
        """QVideoSink에서 받은 프레임을 QPixmap으로 변환하여 표시"""
        if image.isNull():
            return
        self._pixmap = QPixmap.fromImage(image)
        self._video_native = self._pixmap.size()
        self._calc_render_rect()
        self.update()

    def clear_frame(self):
        self._pixmap = None
        self._render_rect = QRect()
        self.update()

    def _calc_render_rect(self):
        """KeepAspectRatio 기준 실제 렌더링 영역 계산"""
        if not self._pixmap or self.size().isEmpty():
            return
        scaled = self._pixmap.size().scaled(self.size(), Qt.KeepAspectRatio)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        self._render_rect = QRect(x, y, scaled.width(), scaled.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._calc_render_rect()

    # ── 크롭 API ──

    def clear_crop(self):
        self._crop_rect = None
        self._crop_origin = None
        self.crop_changed.emit(CropRegion())
        self.update()

    def get_crop_region(self) -> Optional[CropRegion]:
        if not self._crop_rect or not self._crop_rect.isValid():
            return None
        if self._render_rect.isEmpty() or self._video_native.isEmpty():
            return None
        rr = self._render_rect
        # 위젯 좌표 → 비디오 원본 좌표
        scale_x = self._video_native.width() / rr.width()
        scale_y = self._video_native.height() / rr.height()
        rx = self._crop_rect.x() - rr.x()
        ry = self._crop_rect.y() - rr.y()
        crop_x = int(max(0, rx * scale_x))
        crop_y = int(max(0, ry * scale_y))
        crop_w = int(min(self._video_native.width() - crop_x, self._crop_rect.width() * scale_x))
        crop_h = int(min(self._video_native.height() - crop_y, self._crop_rect.height() * scale_y))
        crop_w = max(2, crop_w - (crop_w % 2))
        crop_h = max(2, crop_h - (crop_h % 2))
        return CropRegion(x=crop_x, y=crop_y, width=crop_w, height=crop_h)

    # ── 마우스 이벤트 (크롭) ──

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._crop_origin = event.position().toPoint()
            self._crop_rect = QRect(self._crop_origin, QSize())
            self.update()

    def mouseMoveEvent(self, event):
        if self._crop_origin is None:
            return
        rect = QRect(self._crop_origin, event.position().toPoint()).normalized()
        # 렌더 영역 밖 clamp
        if not self._render_rect.isEmpty():
            rect = rect.intersected(self._render_rect)
        self._crop_rect = rect
        crop = self.get_crop_region()
        if crop:
            self.crop_changed.emit(crop)
        self.update()

    def mouseReleaseEvent(self, event):
        if self._crop_origin is None:
            return
        if event.button() == Qt.LeftButton:
            if self._crop_rect and (self._crop_rect.width() < 10 or self._crop_rect.height() < 10):
                self.clear_crop()
            else:
                crop = self.get_crop_region()
                if crop:
                    self.crop_changed.emit(crop)
            self._crop_origin = None

    def mouseDoubleClickEvent(self, event):
        self.clear_crop()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.clear_crop()
        super().keyPressEvent(event)

    # ── 페인팅 ──

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. 비디오 프레임
        if self._pixmap and not self._render_rect.isEmpty():
            painter.drawPixmap(self._render_rect, self._pixmap)
        else:
            # 빈 화면 안내
            painter.setPen(QColor("#484f58"))
            painter.drawText(self.rect(), Qt.AlignCenter, "파일을 열어주세요")

        # 2. 크롭 오버레이
        if self._crop_rect and self._crop_rect.isValid():
            r = self._crop_rect
            # 어두운 영역
            painter.setBrush(self.OVERLAY)
            painter.setPen(Qt.NoPen)
            painter.drawRect(0, 0, self.width(), r.top())
            painter.drawRect(0, r.bottom(), self.width(), self.height() - r.bottom())
            painter.drawRect(0, r.top(), r.left(), r.height())
            painter.drawRect(r.right(), r.top(), self.width() - r.right(), r.height())
            # 테두리
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(self.BORDER, 2))
            painter.drawRect(r)
            # 모서리
            painter.setBrush(self.HANDLE)
            painter.setPen(Qt.NoPen)
            for pt in [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]:
                painter.drawRect(pt.x() - 3, pt.y() - 3, 6, 6)
            # 해상도
            crop = self.get_crop_region()
            if crop:
                text = f"{crop.width} × {crop.height}"
                font = QFont("Segoe UI", 11, QFont.Bold)
                painter.setFont(font)
                tw = painter.fontMetrics().horizontalAdvance(text) + 12
                th = 24
                tx = r.center().x() - tw // 2
                ty = r.bottom() + 8
                if ty + th > self.height():
                    ty = r.top() - th - 8
                painter.setBrush(QColor(0, 0, 0, 180))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(tx, ty, tw, th, 4, 4)
                painter.setPen(QColor("#58a6ff"))
                painter.drawText(tx, ty, tw, th, Qt.AlignCenter, text)

        painter.end()


# ═══════════════════════════════════════════════
# TimeRangeSlider
# ═══════════════════════════════════════════════

class TimeRangeSlider(QWidget):
    """타임레인지 — In/Out 핸들 + 재생위치 + Seek"""

    range_changed = Signal(float, float)
    seek_requested = Signal(float)

    BAR_BG = QColor("#30363d")
    BAR_RANGE = QColor("#1f6feb")
    HANDLE_IN = QColor("#3fb950")
    HANDLE_OUT = QColor("#f85149")
    HANDLE_PLAY = QColor("#e6edf3")
    HANDLE_W = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)
        self.setMouseTracking(True)
        self._duration: float = 0.0
        self._in_sec: float = 0.0
        self._out_sec: float = 0.0
        self._play_sec: float = 0.0
        self._dragging: Optional[str] = None
        self._seek_dragging = False

    def set_duration(self, sec: float):
        self._duration = max(1.0, sec)
        self._in_sec = 0.0
        self._out_sec = self._duration
        self._play_sec = 0.0
        self.update()

    def set_play_pos(self, sec: float):
        self._play_sec = max(0, min(sec, self._duration))
        self.update()

    def get_range(self) -> Tuple[float, float]:
        return (self._in_sec, self._out_sec)

    def _sec_to_x(self, sec: float) -> int:
        if self._duration <= 0:
            return self.HANDLE_W
        w = self.width() - self.HANDLE_W * 2
        return int(self.HANDLE_W + (sec / self._duration) * w)

    def _x_to_sec(self, x: int) -> float:
        w = self.width() - self.HANDLE_W * 2
        if w <= 0:
            return 0.0
        return max(0.0, min(self._duration, ((x - self.HANDLE_W) / w) * self._duration))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            ox = self._sec_to_x(self._out_sec)
            ix = self._sec_to_x(self._in_sec)
            if abs(pos.x() - ox) <= self.HANDLE_W:
                self._dragging = "out"
            elif abs(pos.x() - ix) <= self.HANDLE_W:
                self._dragging = "in"
            else:
                self._seek_dragging = True
                self.seek_requested.emit(self._x_to_sec(pos.x()))

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self._dragging == "in":
            self._in_sec = max(0.0, min(self._x_to_sec(pos.x()), self._out_sec - 0.5))
            self.range_changed.emit(self._in_sec, self._out_sec)
        elif self._dragging == "out":
            self._out_sec = min(self._duration, max(self._x_to_sec(pos.x()), self._in_sec + 0.5))
            self.range_changed.emit(self._in_sec, self._out_sec)
        elif self._seek_dragging:
            self.seek_requested.emit(self._x_to_sec(pos.x()))
        else:
            ix, ox = self._sec_to_x(self._in_sec), self._sec_to_x(self._out_sec)
            self.setCursor(Qt.PointingHandCursor if (abs(pos.x() - ix) <= self.HANDLE_W or abs(pos.x() - ox) <= self.HANDLE_W) else Qt.ArrowCursor)
        self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = None
        self._seek_dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bar_y, bar_h = 16, 8
        ix = self._sec_to_x(self._in_sec)
        ox = self._sec_to_x(self._out_sec)
        px = self._sec_to_x(self._play_sec)

        painter.setBrush(self.BAR_BG)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.HANDLE_W, bar_y, self.width() - self.HANDLE_W * 2, bar_h, 4, 4)
        if ox > ix:
            painter.setBrush(self.BAR_RANGE)
            painter.drawRect(ix, bar_y, ox - ix, bar_h)
        painter.setBrush(self.HANDLE_IN)
        painter.drawRect(ix - self.HANDLE_W // 2, bar_y - 2, self.HANDLE_W, bar_h + 4)
        painter.setBrush(self.HANDLE_OUT)
        painter.drawRect(ox - self.HANDLE_W // 2, bar_y - 2, self.HANDLE_W, bar_h + 4)
        if 0 < px < self.width():
            painter.setBrush(self.HANDLE_PLAY)
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.drawRect(px - 2, bar_y - 4, 4, bar_h + 8)
        painter.setPen(QColor("#8b949e"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(self.HANDLE_W, bar_y + bar_h + 14, format_time(self._in_sec))
        painter.drawText(self.width() - self.HANDLE_W - 60, bar_y + bar_h + 14, format_time(self._out_sec))
        painter.setPen(QColor("#e6edf3"))
        painter.drawText(px - 20, bar_y - 8, 40, 14, Qt.AlignCenter, format_time(self._play_sec))
        painter.end()


# ═══════════════════════════════════════════════
# VideoViewer
# ═══════════════════════════════════════════════

class VideoViewer(QWidget):
    """비디오 뷰어 — QVideoSink 프레임 + VideoCanvas(크롭내장) + 타임슬라이더"""

    crop_changed = Signal(CropRegion)
    range_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path: Optional[str] = None
        self._duration_sec: float = 0.0
        self._setup_ui()
        self._setup_player()

    def _setup_ui(self):
        self.setStyleSheet("background-color: #0d1117;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 헤더
        header = QWidget()
        header.setStyleSheet("background-color: #16181c; border-bottom: 1px solid #30363d;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(8, 4, 8, 4)
        title = QLabel("🎬 비디오 뷰어")
        title.setProperty("cssClass", "title")
        hl.addWidget(title)
        self.info_label = QLabel("파일을 열어주세요")
        self.info_label.setProperty("cssClass", "subtitle")
        hl.addWidget(self.info_label, stretch=1)
        self.resolution_label = QLabel("크롭: --x--")
        self.resolution_label.setProperty("cssClass", "badge")
        hl.addWidget(self.resolution_label)
        layout.addWidget(header)

        # 비디오 캔버스 (프레임+크롭 통합)
        self.canvas = VideoCanvas()
        self.canvas.crop_changed.connect(self._on_crop_changed)
        layout.addWidget(self.canvas, stretch=1)

        # 재생 컨트롤
        ctrl = QWidget()
        ctrl.setStyleSheet("background-color: #16181c; border-top: 1px solid #30363d;")
        cl = QHBoxLayout(ctrl)
        cl.setContentsMargins(8, 4, 8, 4)
        self.play_btn = QPushButton()
        self.play_btn.setFixedSize(26, 26)
        self.play_btn.setStyleSheet("QPushButton { font-size: 13px; font-weight: bold; background: #21262d; border: 2px solid #ffd700; border-radius: 4px; color: #ffd700; padding: 0px; } QPushButton:hover { background: #30363d; border-color: #ffec80; color: #ffec80; }")
        self.play_btn.clicked.connect(self._toggle_play)
        cl.addWidget(self.play_btn)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        cl.addWidget(self.time_label)
        cl.addStretch()
        self.dur_label = QLabel("총 --:--:--")
        self.dur_label.setProperty("cssClass", "subtitle")
        cl.addWidget(self.dur_label)
        layout.addWidget(ctrl)

        # 타임레인지
        ts = QWidget()
        ts.setStyleSheet("background-color: #16181c; border-top: 1px solid #30363d;")
        tsl = QVBoxLayout(ts)
        tsl.setContentsMargins(8, 4, 8, 4)
        self.time_slider = TimeRangeSlider()
        self.time_slider.range_changed.connect(self._on_range_changed)
        self.time_slider.seek_requested.connect(self._on_seek)
        tsl.addWidget(self.time_slider)
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("전체 선택")
        reset_btn.setFixedHeight(22)
        reset_btn.clicked.connect(self._reset_range)
        btn_row.addWidget(reset_btn)
        self.range_label = QLabel("In: 00:00:00 | Out: 00:00:00")
        self.range_label.setProperty("cssClass", "subtitle")
        btn_row.addStretch()
        btn_row.addWidget(self.range_label)
        tsl.addLayout(btn_row)
        layout.addWidget(ts)

    def _setup_player(self):
        self.player = QMediaPlayer()
        # 오디오 출력
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)
        self.player.setAudioOutput(self.audio_output)
        # VideoSink로 프레임 직접 수신
        self.sink = QVideoSink()
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.playbackStateChanged.connect(self._on_playback_state)
        self.player.errorOccurred.connect(self._on_error)

    # ── 프레임 수신 ──

    def _on_frame(self, frame):
        """QVideoSink에서 새 프레임 수신 → VideoCanvas로"""
        image = frame.toImage()
        self.canvas.set_frame(image)

    # ── Public API ──

    def load_video(self, path: str):
        """파일 로드 — 정지 상태로 첫 프레임 표시"""
        self._current_path = path
        self.canvas.clear_crop()
        self.player.setSource(QUrl.fromLocalFile(path))
        # 정지 상태로 대기 — 재생버튼 누르면 재생
        self.player.pause()
        self.info_label.setText(f"📄 {os.path.basename(path)}")

    def unload(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.canvas.clear_frame()

    def get_crop_region(self) -> Optional[CropRegion]:
        return self.canvas.get_crop_region()

    def get_time_range(self) -> Tuple[float, float]:
        return self.time_slider.get_range()

    # ── 재생 ──

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_playback_state(self, state):
        self.play_btn.setText("||" if state == QMediaPlayer.PlayingState else ">")

    def _on_position_changed(self, ms: int):
        sec = ms / 1000.0
        self.time_slider.set_play_pos(sec)
        self.time_label.setText(f"{format_time(sec)} / {format_time(self._duration_sec)}")

    def _on_duration_changed(self, ms: int):
        self._duration_sec = ms / 1000.0
        self.time_slider.set_duration(self._duration_sec)
        self.dur_label.setText(f"총 {format_time(self._duration_sec)}")

    def _on_media_status(self, status):
        if status == QMediaPlayer.LoadedMedia:
            # 로드 완료 → 첫 프레임 표시 (pause 상태이므로 position=0 프레임)
            pass
        elif status == QMediaPlayer.EndOfMedia:
            # 재생 끝 → 마지막 프레임 유지 (검은화면 방지)
            self.player.pause()
            dur = self.player.duration()
            if dur > 0:
                # 끝에서 200ms 전으로 seek → 마지막 프레임
                self.player.setPosition(max(0, dur - 200))

    def _on_error(self, error, error_str):
        print(f"[MediaPlayer Error] {error}: {error_str}")

    def _on_seek(self, sec: float):
        """슬라이더 Seek"""
        self.player.setPosition(int(sec * 1000))

    def _on_crop_changed(self, crop: CropRegion):
        self.resolution_label.setText(f"✂️ {crop.resolution_str()}" if crop and crop.is_valid() else "크롭: --x--")
        self.crop_changed.emit(crop)

    def _on_range_changed(self, in_sec: float, out_sec: float):
        self.range_label.setText(f"In: {format_time(in_sec)} | Out: {format_time(out_sec)}")
        self.range_changed.emit(in_sec, out_sec)

    def _reset_range(self):
        self.time_slider.set_duration(self._duration_sec)
