# 🖥️ DPU Scenario DB & Viewer

SoC DPU(Display Processing Unit) 시나리오를 YAML로 정의하고, 정적 HTML 토폴로지 다이어그램으로 시각화하는 도구입니다.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-green)
![License](https://img.shields.io/badge/License-Internal-orange)

## Features

- **YAML 기반 시나리오 정의** — DPU 16-RDMA 레이어 할당, 버퍼 속성, 클럭 정보
- **정적 HTML 생성** — 빌드 도구 없이 Python만으로 독립 실행 가능한 HTML 생성
- **Interactive 토폴로지 다이어그램** — Source IP → Buffer → DPU(RDMA) → Display 하드웨어 흐름
- **Layer 테이블** — 전체 RDMA 포트 할당 현황을 테이블로 한눈에 확인
- **Multi-Project 지원** — `scenarios/{project}/` 구조로 과제별 시나리오 관리
- **GitHub Pages 호환** — `docs/` 폴더 그대로 배포

## Quick Start

```bash
# 1. HTML 생성 (venv 자동 생성)
python run.py

# 2. 브라우저에서 열기
# docs/index.html 더블클릭 또는:
start docs/index.html        # Windows
open docs/index.html          # macOS
```

## Project Structure

```
├── run.py                      # 통합 실행기 (venv → 변환)
├── scenarios/                  # 시나리오 YAML 저장소
│   └── projectA/               #   과제별 서브디렉토리
│       ├── 01_lcd_idle.yaml
│       ├── 02_video_playback.yaml
│       ├── 03_camera_preview.yaml
│       ├── 04_camera_recording.yaml
│       └── 05_pip_mode.yaml
├── scripts/                    # Python 파이프라인
│   ├── requirements.txt
│   ├── schema.py               #   Pydantic 데이터 모델
│   ├── processor.py            #   YAML → HTML 변환 엔진
│   └── templates/              #   Jinja2 HTML 템플릿
│       ├── index.html.j2       #     프로젝트 선택 대시보드
│       ├── project_index.html.j2 #   시나리오 목록
│       └── viewer.html.j2      #     토폴로지 뷰어
└── docs/                       # 생성된 HTML (GitHub Pages root)
    ├── index.html
    └── {project}/
        ├── index.html
        └── views/*.html
```

## Scenario YAML Format

```yaml
name: "Video_Playback"
description: "Full-screen video playback with UI overlay"
clock:
  min_pixel_clock_mhz: 150.0
  min_axi_clock_mhz: 200.0
  aclk_mhz: 400.0
  mif_min_freq_mhz: 845.0
display:
  resolution: "FHD+"
  width: 1080
  height: 2400
  fps: 60
layers:
  - name: "Video_Y"
    source: "CODEC"
    format: "NV12"
    format_category: "YUV"
    size: { width: 1920, height: 1080 }
    bw: { original_gbps: 0.37, compressed_gbps: 0.22 }
    compression_type: "SBWC"
    rdma_index: 0
  - name: "UI_Overlay"
    source: "GPU"
    format: "ARGB8888"
    format_category: "ARGB"
    size: { width: 1080, height: 2400 }
    bw: { original_gbps: 0.59, compressed_gbps: 0.35 }
    compression_type: "SAJC"
    rdma_index: 1
```

## Adding a New Project

```bash
# 1. 프로젝트 디렉토리 생성
mkdir scenarios/projectB

# 2. 시나리오 YAML 작성 (위 포맷 참고)
# 3. HTML 재생성
python run.py
```

## GitHub Pages 배포

1. Repository Settings → Pages → Source: **Deploy from a branch**
2. Branch: `main`, Folder: `/docs`
3. YAML + HTML을 함께 커밋 & push

## Dependencies

- Python 3.10+
- PyYAML, Pydantic v2, Jinja2 (자동 설치)
