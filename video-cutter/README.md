# Video Cutter Pro 🎬

**PySide6 기반 FFmpeg GUI 프론트엔드** — 직관적인 UI로 영상 자르기/크롭/인코딩.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-green)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11%20%7C%20macOS%2014%2B-blue)

---

## ✨ 주요 기능

### 1. 작업 모드 (Smart Mode Selector)

| 모드 | 방식 | 특징 |
|------|------|------|
| ⚡ **라이트닝 컷** | Stream Copy (`-c copy`) | 화질 손실 **0%**, 원본 그대로 초고속 추출 |
| 💎 **무손실** | HEVC NVENC `-qp 0` | 수학적 완전 무손실, 고용량 |
| 🌟 **시각적 무손실** | HEVC NVENC `-cq 14~16` | 인간 눈으로 판별 불가능, 고효율 압축 |

### 2. 인터랙티브 크롭
- 비디오 화면 위 마우스 **드래그**로 자르기 영역 선택
- QRubberBand로 실시간 선택 영역 표시
- 선택 영역 해상도 자동 계산 (예: `1920×1080 → 1280×720`)
- **더블클릭**으로 크롭 초기화

### 3. 하드웨어 가속
- NVIDIA NVENC (HEVC) 인코딩 지원
- RTX 3090 리소스 활용 시각적 표시
- NVENC 미사용 시 CPU(x265) 자동 fallback

### 4. 실시간 모니터링
- 인코딩 진행률 프로그레스바
- 실시간 FPS/속도 표시
- FFmpeg 전체 로그 출력

---

## 📦 설치

### Windows

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. FFmpeg (선택) — ffmpeg.exe를 ffmpeg/ 폴더에 복사
#    또는 dist/VideoCutterPro.exe (ffmpeg 내장, 단독 실행)

# 3. 실행
python main.py
```

### macOS (Apple Silicon M1/M2/M3/M4)

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 자동 빌드 (ffmpeg 자동 다운로드 + PyInstaller 패키징)
chmod +x build_mac.sh
./build_mac.sh

# 3. 실행 (생성된 .app 번들)
open dist_mac/VideoCutterPro.app
```

> `build_mac.sh`가 자동으로 ffmpeg ARM64 바이너리를 다운로드하여 앱에 번들링합니다.  
> 결과물은 **단일 .app 번들**로, 외부 의존성 없이 독립 실행 가능합니다.

### macOS — GitHub Actions 자동 빌드 (권장)

```bash
# 1. GitHub에 리포지토리 push
git remote add origin https://github.com/사용자명/VideoCutterPro.git
git push origin main

# 2. 태그 생성 → 자동 빌드
git tag v1.0.0
git push origin v1.0.0

# 3. GitHub Actions 탭 → 빌드 완료 후
#    "VideoCutterPro-macOS" 아티팩트 다운로드
#    → VideoCutterPro.app 단일 파일
```

GitHub Actions가 macOS 클라우드 서버에서 자동으로 `.app`을 빌드합니다.  
Windows 환경에서도 macOS 앱을 배포할 수 있습니다.

### FFmpeg 다운로드 (수동)
- Windows: [ffmpeg.org](https://ffmpeg.org/download.html) — `ffmpeg.exe`
- macOS ARM64: `build_mac.sh`가 자동 다운로드 또는 [evermeet.cx](https://evermeet.cx/ffmpeg/)
- `ffmpeg/` 폴더에 넣으면 빌드 시 번들됨

---

## 🏗️ 프로젝트 구조

```
video-cutter/
├── main.py                      # 진입점
├── requirements.txt             # PySide6
├── ffmpeg/                      # ffmpeg.exe (portable)
├── src/
│   ├── app.py                   # QApplication 부트스트랩
│   ├── engine/
│   │   ├── models.py            # 데이터 모델 (JobConfig, CropRegion)
│   │   ├── ffmpeg_wrapper.py    # 명령어 템플릿
│   │   └── process_manager.py   # QThread + 진행률 파싱
│   ├── ui/
│   │   ├── main_window.py       # 3분할 메인 윈도우
│   │   ├── file_browser.py      # 파일 탐색기 + 최근 목록
│   │   ├── video_viewer.py      # 비디오 뷰어 + 크롭 오버레이
│   │   ├── task_panel.py        # 작업 패널 (모드/CRF/진행률)
│   │   └── theme.py             # 다크 테마 로더
│   └── utils/
│       └── helpers.py           # 파일 크기, 시간 변환
└── resources/
    └── styles/
        └── dark_theme.qss       # 모던 다크 QSS 테마
```

---

## 🎮 사용법

1. **파일 열기**: 좌측 파일 탐색기에서 비디오 더블클릭
2. **작업 모드 선택**: 우측 패널에서 Lightning Cut / Master Quality 선택
3. **크롭 설정**: 비디오 화면 위를 드래그 (선택사항)
4. **시간 설정**: 시작/종료 시간 지정 (선택사항)
5. **시작 버튼** 클릭: 인코딩 진행
6. 완료 시 출력 파일 정보 표시

---

## 🔧 기술 상세

### 아키텍처

```
사용자 UI (PySide6)
    ↓ 입력
MainWindow (3분할 레이아웃)
    ↓ JobConfig
FFMpegWrapper (명령어 생성)
    ↓ List[str]
ProcessWorker (QThread + subprocess)
    ↓ stderr 파싱
실시간 진행률 → UI 업데이트
```

### FFmpeg 옵션 상세

**라이트닝 컷:**
```bash
ffmpeg -y -i input.mp4 -c copy -map 0 -avoid_negative_ts make_zero output.mp4
```

**무손실 (NVENC):**
```bash
ffmpeg -y -hwaccel cuda -i input.mp4 -c:v hevc_nvenc -qp 0 -preset p7 -tier high -rc vbr -c:a flac output.mkv
```

**시각적 무손실 (NVENC):**
```bash
ffmpeg -y -hwaccel cuda -i input.mp4 -c:v hevc_nvenc -cq 14 -preset p7 -tier high -rc vbr -b:v 0 -c:a aac -b:a 320k output.mp4
```

---

## 📋 개발 로드맵

| 우선순위 | 작업 | 상태 |
|----------|------|------|
| P0 | FFmpeg 엔진 래핑 | ✅ 완료 |
| P1 | UI/UX 디자인 (PySide6) | ✅ 완료 |
| P2 | 비동기 처리 (QThread) | ✅ 완료 |
| P3 | 배포 (PyInstaller) | 📝 예정 |

---

## 📄 라이선스

MIT License
