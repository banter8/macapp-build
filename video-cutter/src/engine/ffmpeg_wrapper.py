"""FFmpeg 명령어 템플릿 — 상황별(Copy/Lossless/CRF) 명령어 생성"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import List, Optional

from .models import CropRegion, JobConfig, WorkMode
from ..utils.helpers import find_ffmpeg_path


class FFMpegWrapper:
    """FFmpeg 명령어 빌더

    사용 예:
        wrapper = FFMpegWrapper(ffmpeg_path="ffmpeg/ffmpeg.exe")
        cmd = wrapper.build_command(job_config)
    """

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or find_ffmpeg_path()

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def build_command(self, config: JobConfig) -> List[str]:
        """JobConfig → FFmpeg 명령어 리스트"""
        cmd = [self.ffmpeg_path, "-y"]  # -y: 덮어쓰기 허용

        # 하드웨어 가속 글로벌 옵션
        if config.use_hardware_accel:
            cmd.extend(["-hwaccel", "cuda"])

        # 입력 파일
        cmd.extend(["-i", config.input_path])

        # 시작 시간
        if config.start_time:
            cmd.extend(["-ss", config.start_time])

        # 종료 시간 / 지속 시간
        if config.end_time and not config.duration:
            cmd.extend(["-to", config.end_time])
        if config.duration:
            cmd.extend(["-t", config.duration])

        # 모드별 인코딩 옵션
        if config.mode == WorkMode.LIGHTNING_CUT:
            cmd.extend(self._lightning_cut_opts(config))
        elif config.mode == WorkMode.MASTER_QUALITY_LOSSLESS:
            cmd.extend(self._lossless_opts(config))
        elif config.mode == WorkMode.MASTER_QUALITY_HIGH:
            cmd.extend(self._high_fidelity_opts(config))

        # 크롭 필터
        filter_parts = []
        if config.crop and config.crop.is_valid():
            filter_parts.append(config.crop.to_ffmpeg_crop())

        # 필터 적용
        if filter_parts:
            cmd.extend(["-vf", ",".join(filter_parts)])

        # 출력 파일
        output_path = config.output_path or config.auto_output_path
        output_dir = os.path.dirname(output_path)
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        cmd.append(output_path)

        return cmd

    def build_command_str(self, config: JobConfig) -> str:
        """디버깅용 명령어 문자열"""
        cmd = self.build_command(config)
        return " ".join(shlex.quote(c) for c in cmd if c)

    # ──────────────────────────────────────────────
    # 모드별 옵션
    # ──────────────────────────────────────────────

    def _lightning_cut_opts(self, config: JobConfig) -> List[str]:
        """A] 라이트닝 컷 — Stream Copy (-c copy)

        화질 손실 0%, 원본 데이터 그대로 추출.
        재인코딩 없음 → 초고속.
        """
        opts: List[str] = [
            "-c", "copy",               # 모든 스트림 copy
            "-map", "0",                 # 모든 스트림 매핑
            "-avoid_negative_ts", "make_zero",
        ]

        # 크롭이 있으면 copy 불가 → 재인코딩 필요
        # → 이 경우 사용자에게 경고 표시 필요 (UI 레벨)
        if config.crop and config.crop.is_valid():
            # Stream Copy + Crop은 FFmpeg에서 불가능
            # 자동으로 libx265 (CPU) fallback
            opts = self._auto_hevc_fallback(config)

        return opts

    def _lossless_opts(self, config: JobConfig) -> List[str]:
        """B-1] 무손실 모드 (Lossless) — 수학적 완전 무손실

        -qp 0 (NVENC), -crf 0 (x265)
        출력: .mkv 권장
        """
        opts: List[str] = []

        if config.use_hardware_accel and self._nvenc_available():
            # NVENC 무손실
            opts = [
                "-c:v", "hevc_nvenc",
                "-qp", "0",              # 수학적 완전 무손실
                "-preset", "p7",         # 최고 품질 프리셋
                "-tier", "high",
                "-rc", "vbr",            # 가변 비트레이트
            ]
        else:
            # CPU x265 무손실 (fallback)
            opts = [
                "-c:v", "libx265",
                "-crf", "0",             # 수학적 완전 무손실
                "-preset", "slow",
                "-x265-params", "lossless=1",
            ]

        # 오디오는 무손실 FLAC으로
        opts.extend(["-c:a", "flac"])

        return opts

    def _high_fidelity_opts(self, config: JobConfig) -> List[str]:
        """B-2] 시각적 무손실 모드 (High Fidelity)

        -cq 14~16: 인간의 눈으로 판별 불가능한 최적화 압축
        """
        cq = max(14, min(16, config.cq_level))  # 14~16 clamp
        opts: List[str] = []

        if config.use_hardware_accel and self._nvenc_available():
            opts = [
                "-c:v", "hevc_nvenc",
                "-cq", str(cq),          # 14~16
                "-preset", "p7",
                "-tier", "high",
                "-rc", "vbr",
                "-b:v", "0",             # 비트레이트 제한 없음
            ]
        else:
            # CPU x265 VMAF 우수 범위
            crf_map = {14: 16, 15: 17, 16: 18}
            crf = crf_map.get(cq, 17)
            opts = [
                "-c:v", "libx265",
                "-crf", str(crf),
                "-preset", "slow",
            ]

        # 오디오는 고품질 AAC
        opts.extend(["-c:a", "aac", "-b:a", "320k"])

        return opts

    def _auto_hevc_fallback(self, config: JobConfig) -> List[str]:
        """크롭 등으로 Stream Copy가 불가능할 때 HEVC fallback"""
        cq = max(14, min(16, config.cq_level))
        opts: List[str] = []

        if config.use_hardware_accel and self._nvenc_available():
            opts = [
                "-c:v", "hevc_nvenc",
                "-cq", str(cq),
                "-preset", "p7",
                "-rc", "vbr",
                "-c:a", "aac", "-b:a", "192k",
            ]
        else:
            opts = [
                "-c:v", "libx265",
                "-crf", "17",
                "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
            ]

        return opts

    # ──────────────────────────────────────────────
    # 유틸리티
    # ──────────────────────────────────────────────

    @staticmethod
    def _nvenc_available() -> bool:
        """NVENC 사용 가능 여부 (기본 True, 실제 체크는 런타임에)

        실제로는 ffmpeg -encoders 출력에서 hevc_nvenc 확인 필요:
            ffmpeg -hide_banner -encoders | findstr hevc_nvenc
        """
        # 항상 True 반환 — 실패 시 FFmpeg가 stderr로 에러 출력
        return True

    @staticmethod
    def probe_command(ffmpeg_path: str = "ffmpeg") -> List[str]:
        """ffprobe (또는 ffmpeg)로 영상 정보 조회 명령어"""
        return [
            ffmpeg_path,
            "-hide_banner",
            "-i", "INPUT",
            "-f", "null",
            "-",
        ]

    # ──────────────────────────────────────────────
    # 썸네일 추출
    # ──────────────────────────────────────────────

    def thumbnail_command(self, video_path: str, time_sec: float = 1.0, max_width: int = 1280) -> List[str]:
        """비디오의 특정 시점 프레임을 PNG로 추출 (stdout 출력)

        Args:
            video_path: 비디오 파일 경로
            time_sec: 추출할 시점 (초)
            max_width: 최대 너비 (비율 유지)

        Returns:
            subprocess 실행용 명령어 리스트
        """
        return [
            self.ffmpeg_path,
            "-ss", str(time_sec),
            "-i", video_path,
            "-vframes", "1",
            "-vf", f"scale={max_width}:-2",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-",
        ]

    @staticmethod
    def probe_duration_command(ffmpeg_path: str = "ffmpeg") -> List[str]:
        """비디오 길이 조회 명령어"""
        return [
            ffmpeg_path,
            "-hide_banner",
            "-i", "INPUT",
            "-f", "null",
            "-",
        ]
