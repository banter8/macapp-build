"""subprocess 기반 FFmpeg 실행 + 실시간 진행률 파싱

QThread를 사용하여 UI 블로킹 없이 FFmpeg 실행.
stderr의 "time=HH:MM:SS.ms" 형식을 파싱하여 진행률(%) 계산.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QThread, Signal

from .ffmpeg_wrapper import FFMpegWrapper
from .models import JobConfig, ProcessStatus, VideoInfo


# ──────────────────────────────────────────────
# 진행률 파싱
# ──────────────────────────────────────────────

_TIME_RE = re.compile(rb"time=(\d+):(\d+):(\d+)\.(\d+)")
_SPEED_RE = re.compile(rb"speed=\s*([\d.]+)x")
_FRAME_RE = re.compile(rb"frame=\s*(\d+)")
_FPS_RE = re.compile(rb"fps=\s*([\d.]+)")
_BITRATE_RE = re.compile(rb"bitrate=\s*([\d.]+)kb/s")
_DURATION_RE = re.compile(rb"Duration: (\d+):(\d+):(\d+)\.(\d+)")
_SIZE_RE = re.compile(rb"size=\s*(\d+)kB")


class ProcessWorker(QThread):
    """FFmpeg 프로세스를 별도 스레드에서 실행"""

    # ── 시그널 ─────────────────────────────
    progress_changed = Signal(float, str)        # 진행률(0~100), 상태 문자열
    log_line = Signal(str)                        # 로그 라인
    finished = Signal(bool, str)                  # 성공 여부, 메시지
    hw_accel_status = Signal(bool)                # NVENC 사용 여부

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False
        self._config: Optional[JobConfig] = None
        self._duration_sec: float = 0.0

    def configure(self, config: JobConfig):
        """작업 설정"""
        self._config = config
        self._cancelled = False

    def cancel(self):
        """작업 취소"""
        self._cancelled = True
        if self._process and self._process.poll() is None:
            if os.name == "nt":
                self._process.terminate()
            else:
                os.kill(self._process.pid, signal.SIGTERM)

    def run(self):
        """QThread 실행 (별도 스레드)"""
        if not self._config:
            self.finished.emit(False, "작업 설정이 없습니다.")
            return

        wrapper = FFMpegWrapper()
        cmd = wrapper.build_command(self._config)
        cmd_str = " ".join(cmd)
        self.log_line.emit(f"[명령어] {cmd_str}")
        self.log_line.emit("[시작] FFmpeg 프로세스 시작...")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except FileNotFoundError:
            self.finished.emit(False, f"FFmpeg를 찾을 수 없습니다: {self._ffmpeg_path()}")
            return
        except Exception as e:
            self.finished.emit(False, f"프로세스 시작 실패: {e}")
            return

        # 진행률 파싱 (stderr)
        self._parse_progress(self._process)

    def _parse_progress(self, process: subprocess.Popen):
        """stderr에서 진행률 파싱"""
        stderr_lines: List[bytes] = []

        for line in iter(process.stderr.readline, b""):
            if self._cancelled:
                process.terminate()
                self.finished.emit(False, "사용자에 의해 취소됨")
                return

            stderr_lines.append(line)

            # Duration 파싱 (최초 1회)
            if self._duration_sec == 0.0:
                m = _DURATION_RE.search(line)
                if m:
                    h, mi, s, ms = map(int, m.groups())
                    self._duration_sec = h * 3600 + mi * 60 + s + ms / 100.0
                    self.log_line.emit(f"[정보] 총 길이: {self._format_time(self._duration_sec)}")

            # 진행률 파싱
            tm = _TIME_RE.search(line)
            if tm and self._duration_sec > 0:
                h, mi, s, ms = map(int, tm.groups())
                current_sec = h * 3600 + mi * 60 + s + ms / 100.0
                progress = min(100.0, (current_sec / self._duration_sec) * 100.0)

                # 상태 문자열 조립
                status_parts = [f"{progress:.1f}%"]
                sp = _SPEED_RE.search(line)
                if sp:
                    status_parts.append(f"속도: {sp.group(1).decode()}x")
                fr = _FPS_RE.search(line)
                if fr:
                    status_parts.append(f"FPS: {fr.group(1).decode()}")
                fr_count = _FRAME_RE.search(line)
                if fr_count:
                    status_parts.append(f"프레임: {fr_count.group(1).decode()}")

                self.progress_changed.emit(progress, " | ".join(status_parts))

            # 전체 로그 저장 (최근 100줄)
            decoded = line.decode("utf-8", errors="replace").rstrip()
            if decoded.strip():
                self.log_line.emit(decoded)

        process.wait()

        # 완료 처리
        exit_code = process.returncode
        if self._cancelled:
            self.finished.emit(False, "사용자에 의해 취소됨")
        elif exit_code == 0:
            self.progress_changed.emit(100.0, "완료!")
            self.finished.emit(True, "작업이 성공적으로 완료되었습니다.")
        else:
            error_msg = f"FFmpeg 오류 (코드: {exit_code})"
            # 마지막 로그에서 에러 메시지 추출
            for line in stderr_lines[-10:]:
                decoded = line.decode("utf-8", errors="replace").strip()
                if "error" in decoded.lower():
                    error_msg += f"\n  {decoded}"
            self.finished.emit(False, error_msg)

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    @staticmethod
    def _ffmpeg_path() -> str:
        return "ffmpeg/ffmpeg.exe"

    @staticmethod
    def _format_time(sec: float) -> str:
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


class ProcessManager:
    """ProcessWorker를 관리하는 고수준 인터페이스

    UI 컴포넌트는 이 클래스만 참조.
    """

    def __init__(self):
        self._worker: Optional[ProcessWorker] = None
        self._status: ProcessStatus = ProcessStatus.IDLE

    @property
    def status(self) -> ProcessStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._status == ProcessStatus.RUNNING

    def connect_signals(
        self,
        on_progress: Callable,
        on_log: Callable,
        on_finished: Callable,
        on_hw_accel: Callable = None,
    ):
        """시그널 연결"""
        if self._worker is None:
            self._worker = ProcessWorker()
        self._worker.progress_changed.connect(on_progress)
        self._worker.log_line.connect(on_log)
        self._worker.finished.connect(self._on_finished_wrapper(on_finished))
        if on_hw_accel:
            self._worker.hw_accel_status.connect(on_hw_accel)

    def start(self, config: JobConfig):
        """작업 시작"""
        if self._worker is None:
            self._worker = ProcessWorker()
        self._status = ProcessStatus.RUNNING
        self._worker.configure(config)
        self._worker.start()

    def cancel(self):
        """작업 취소"""
        if self._worker:
            self._worker.cancel()
        self._status = ProcessStatus.CANCELLED

    def _on_finished_wrapper(self, callback: Callable):
        """finished 시그널 래퍼 — 상태 업데이트 후 콜백"""
        def wrapper(success: bool, message: str):
            self._status = ProcessStatus.COMPLETED if success else ProcessStatus.FAILED
            callback(success, message)
        return wrapper
