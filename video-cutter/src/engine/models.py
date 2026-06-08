"""데이터 모델 — 작업 설정, 영상 정보, 크롭 영역"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class ProcessStatus(Enum):
    """작업 상태"""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class WorkMode(Enum):
    """작업 모드"""
    LIGHTNING_CUT = "lightning_cut"       # Stream Copy (-c copy)
    MASTER_QUALITY_LOSSLESS = "lossless"   # 무손실 (-qp 0)
    MASTER_QUALITY_HIGH = "high_fidelity"  # 시각적 무손실 (-cq 14~16)


@dataclass
class CropRegion:
    """크롭 영역 (픽셀 좌표)"""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0

    def to_ffmpeg_crop(self) -> str:
        """FFmpeg crop 필터 문자열 반환"""
        if not self.is_valid():
            return ""
        return f"crop={self.width}:{self.height}:{self.x}:{self.y}"

    def resolution_str(self) -> str:
        return f"{self.width}x{self.height}" if self.is_valid() else ""


@dataclass
class VideoInfo:
    """입력 영상의 기본 정보"""
    path: str = ""
    width: int = 0
    height: int = 0
    duration_sec: float = 0.0
    fps: float = 0.0
    codec: str = ""
    bitrate: str = ""

    @property
    def filename(self) -> str:
        return os.path.basename(self.path) if self.path else ""

    @property
    def resolution_str(self) -> str:
        return f"{self.width}x{self.height}" if self.width and self.height else ""

    @property
    def duration_str(self) -> str:
        """HH:MM:SS 형식"""
        if self.duration_sec <= 0:
            return "--:--:--"
        h = int(self.duration_sec // 3600)
        m = int((self.duration_sec % 3600) // 60)
        s = int(self.duration_sec % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


@dataclass
class JobConfig:
    """단일 인코딩 작업 설정"""
    # 입력
    input_path: str = ""
    output_path: str = ""

    # 시간
    start_time: Optional[str] = None  # "HH:MM:SS" or None
    end_time: Optional[str] = None    # "HH:MM:SS" or None
    duration: Optional[str] = None    # "HH:MM:SS" or None

    # 모드
    mode: WorkMode = WorkMode.LIGHTNING_CUT

    # 크롭
    crop: Optional[CropRegion] = None

    # 마스터 퀄리티 옵션
    cq_level: int = 14  # -cq 값 (14~16, 기본 14)

    # NVENC 가속
    use_hardware_accel: bool = True

    # 출력 오버라이드
    output_extension: str = ".mp4"
    # 손실 기반 무손실: 자동으로 .mkv (qp 0는 mkv에서만 무손실 보장)
    # 일반 HEVC: .mp4

    def __post_init__(self):
        """기본값 설정"""
        if self.output_extension == "":
            if self.mode == WorkMode.MASTER_QUALITY_LOSSLESS:
                self.output_extension = ".mkv"
            else:
                self.output_extension = ".mp4"

    @property
    def auto_output_path(self) -> str:
        """입력 경로 기반 출력 경로 자동 생성"""
        if not self.input_path:
            return ""
        base, ext = os.path.splitext(self.input_path)
        suffix = {
            WorkMode.LIGHTNING_CUT: "_cut",
            WorkMode.MASTER_QUALITY_LOSSLESS: "_lossless",
            WorkMode.MASTER_QUALITY_HIGH: "_master",
        }.get(self.mode, "_output")
        return f"{base}{suffix}{self.output_extension}"

    def to_dict(self) -> dict:
        return {
            "input": self.input_path,
            "output": self.output_path or self.auto_output_path,
            "mode": self.mode.value,
            "start": self.start_time,
            "end": self.end_time,
            "duration": self.duration,
            "crop": self.crop.to_ffmpeg_crop() if self.crop else "",
            "cq": self.cq_level,
            "hw_accel": self.use_hardware_accel,
        }
