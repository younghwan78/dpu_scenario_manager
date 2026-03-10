# DPU Scenario Viewer — Design Document

## 1. Overview

DPU Scenario Viewer는 SoC Display Processing Unit의 시나리오별 RDMA 레이어 할당 상태를 시각화하는 도구입니다.

**핵심 설계 원칙:**
- **Zero Build** — Node.js, webpack 등 프론트엔드 빌드 도구 없이 Python만으로 완결
- **Self-Contained HTML** — 생성된 HTML 파일 하나로 다이어그램 + 데이터 + 스타일 모두 포함
- **Local = Remote** — 로컬 더블클릭과 GitHub Pages 배포 결과가 100% 동일

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Scenario YAML                                               │
│   scenarios/{project}/*.yaml                                │
└──────────────┬──────────────────────────────────────────────┘
               │ PyYAML + Pydantic
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Python Pipeline (scripts/)                                   │
│                                                              │
│  schema.py     Pydantic v2 모델 (DpuScenario, Layer, ...)   │
│  processor.py  YAML → Jinja2 렌더링 → HTML 출력             │
│                                                              │
│  templates/                                                  │
│    index.html.j2          프로젝트 선택 대시보드             │
│    project_index.html.j2  시나리오 카드 목록                 │
│    viewer.html.j2         SVG 토폴로지 + 테이블 + 패널      │
└──────────────┬──────────────────────────────────────────────┘
               │ Jinja2 렌더링
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Static HTML Output (docs/)                                   │
│                                                              │
│  index.html                     프로젝트 대시보드            │
│  {project}/index.html           시나리오 목록                │
│  {project}/views/{name}.html    토폴로지 뷰어               │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model

### 3.1 Scenario YAML Schema

```
DpuScenario
├── name: str
├── description: str
├── clock: ClockInfo
│   ├── min_pixel_clock_mhz: float
│   ├── min_axi_clock_mhz: float
│   ├── aclk_mhz: float
│   └── mif_min_freq_mhz: float
├── display: DisplayInfo
│   ├── resolution: str       ("FHD+", "WQHD+")
│   ├── width: int
│   ├── height: int
│   └── fps: int
└── layers: list[Layer]
    ├── name: str             ("Video_Y", "Wallpaper")
    ├── source: str           ("GPU", "ISP", "CODEC")
    ├── format: str           ("NV12", "ARGB8888")
    ├── format_category: str  ("YUV" | "ARGB")
    ├── size: BufferSize
    │   ├── width: int
    │   └── height: int
    ├── bw: BufferBW
    │   ├── original_gbps: float
    │   └── compressed_gbps: float?
    ├── compression_type: str ("SBWC", "SAJC", "None")
    └── rdma_index: int       (0~15)
```

### 3.2 설계 결정: 확장 가능한 타입

- `source`, `format`, `compression_type` 등은 `Literal` 대신 **`str`** 사용
- 새 포맷이나 소스 IP 추가 시 코드 수정 없이 YAML만 변경 가능
- 향후 HW 제약 검증이 필요하면 `@model_validator` 추가로 확장

---

## 4. HTML Generation Pipeline

### 4.1 Multi-Project Discovery

```python
scenarios/
├── projectA/    ← _discover_projects()가 자동 탐색
│   ├── 01_lcd_idle.yaml
│   └── ...
└── projectB/
    └── ...
```

`processor.py`의 `_discover_projects()`가 `scenarios/` 하위에서 `*.yaml`이 있는 디렉토리를 자동 탐색합니다.

### 4.2 렌더링 흐름

1. **YAML 로드** → `PyYAML`로 파싱
2. **Pydantic 검증** → `DpuScenario` 모델로 변환
3. **컨텍스트 빌드** → 시나리오 데이터를 JSON 직렬화 + 메타데이터 계산
4. **Jinja2 렌더링** → 템플릿에 데이터 주입 → HTML 파일 출력
5. **JSON 인라인** → `const SCENARIO = {...};`로 HTML 내 JS 변수에 직접 주입

### 4.3 출력 디렉토리 구조

```
docs/
├── index.html                          ← 프로젝트 선택
├── projectA/
│   ├── index.html                      ← 시나리오 목록
│   └── views/
│       ├── lcd_idle.html               ← 뷰어 (self-contained)
│       └── ...
└── projectB/
    └── ...
```

---

## 5. Viewer Template 설계 (`viewer.html.j2`)

### 5.1 전체 레이아웃

```
┌─── Header (시나리오 이름 + 뒤로가기) ──────────────────────┐
├─── Main Area ──────────────────────────────┬── Side Panel ──┤
│                                            │  Display Info  │
│        SVG Topology Canvas                 │  Clock Table   │
│    Source → Buffer → DPU → Display         │  Legend        │
│                                            │  Summary       │
├─── Bottom Panel ───────────────────────────┴────────────────┤
│    Layer Table (RDMA, Name, Source, Format, Size, BW, Comp)  │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 SVG 토폴로지 다이어그램

순수 SVG로 구현 (외부 라이브러리 없음):

**노드 유형:**

| 노드 | 역할 | 배경색 |
|------|------|--------|
| Source | GPU/ISP/CODEC 소스 IP | `#2a2a3e` (Dark Grey) |
| Buffer | 각 레이어의 버퍼 | YUV: `#3d2e1a` / ARGB: `#1a3d1e` |
| DPU | RDMA 포트 블록 | `#2d1f4e` (Purple) |
| Display | 출력 디스플레이 | `#1a2632` (Dark Blue) |

**레이아웃 알고리즘:**
- 4열 고정 배치: Source → Buffer → DPU → Display (COL_GAP: 100px)
- DPU 높이: `MIN_VISUAL_SLOTS(10)` 기준으로 통일 (시나리오 간 동일 스케일)
- 각 노드는 캔버스 내 수직 중앙 정렬
- Bézier 곡선 엣지 (`C` 커맨드)

**엣지 스타일:**

| 조건 | 색상 | 선 스타일 |
|------|------|----------|
| YUV 데이터 | Red `#E53935` | solid |
| YUV + 압축 | Red `#E53935` | dashed (6,4) |
| ARGB 데이터 | Blue `#1E88E5` | solid |
| ARGB + 압축 | Blue `#1E88E5` | dashed (6,4) |
| DPU → Display | Purple `#a78bfa` | solid (두꺼움) |

**압축 표시:**
- Buffer 노드: `<pattern>` 기반 빗금(hatching) 오버레이
- Edge: `stroke-dasharray` 점선
- Edge 레이블: 압축된 엣지에만 "SBWC"/"SAJC" 표시

### 5.3 Interactive 기능

- **Buffer 노드 hover** → 툴팁 (Source, Format, Size, BW, Compression, RDMA 상세정보)
- **테이블 행 hover** → 대응 Edge/Buffer/Port가 캔버스에서 하이라이트 (glow 효과)
- **반응형 리사이즈** → `resizeCanvas()`로 SVG를 컨테이너 중앙 fit

### 5.4 다이어그램 크기 통일

```javascript
const MIN_VISUAL_SLOTS = 10;
const visualSlots = Math.max(numPorts, MIN_VISUAL_SLOTS);
const dpuH = visualSlots * DPU_PORT_H + DPU_PAD * 2;
```

레이어 수에 관계없이 DPU 블록 높이를 최소 10 슬롯으로 고정하여, LCD Idle(3개)이든 PIP Mode(10개)든 동일한 스케일로 렌더링합니다.

---

## 6. Side Panel

| 섹션 | 내용 |
|------|------|
| Display | 해상도 뱃지 (FHD+, 1080×2400, 60fps) |
| Clock (MHz) | min pixel/AXI clock, ACLK, MIF min freq 테이블 |
| Legend — Format | YUV(Orange), ARGB(Green) 색상 범례 |
| Legend — Compression | 압축(빗금+점선) vs 비압축(실선) 범례 |
| Summary | 총 레이어 수, 원본/유효 BW, 활성 Source IP 목록 |

---

## 7. Layer Table (Bottom Panel)

하단 고정 테이블로 전체 RDMA 할당 현황을 표시:

| 컬럼 | 설명 |
|------|------|
| RDMA | 포트 인덱스 (보라색 강조) |
| Layer Name | 버퍼 이름 |
| Source | GPU/ISP/CODEC |
| Format | NV12, ARGB8888 등 |
| Category | YUV/ARGB 뱃지 (색상 구분) |
| Size | 해상도 (width×height) |
| BW (orig) | 원본 대역폭 (GB/s) |
| BW (comp) | 압축 후 대역폭 (초록색, 없으면 —) |
| Compression | SBWC/SAJC/None 뱃지 (색상 구분) |

테이블 행 hover 시 `highlightEdge()` 호출로 캔버스 연동.

---

## 8. 네비게이션 구조

```
docs/index.html           ← 프로젝트 선택
    ↓ 클릭
docs/{project}/index.html ← 시나리오 목록  ← "← All Projects"
    ↓ 클릭
docs/{project}/views/{name}.html           ← "← {project}"
```

---

## 9. 확장 포인트

| 영역 | 확장 방법 |
|------|----------|
| **새 Source IP** | YAML에 `source: "NEW_IP"` 추가 (코드 변경 없음) |
| **새 포맷** | YAML에 `format: "P010"` 추가 (코드 변경 없음) |
| **HW 검증** | `schema.py`에 `@model_validator` 추가 |
| **새 프로젝트** | `scenarios/{name}/` 폴더 + YAML 추가 후 `run.py` |
| **스타일 변경** | `viewer.html.j2`의 CSS/COLOR 상수 수정 |
| **새 메타 필드** | `Layer` 모델에 필드 추가 → 템플릿에서 참조 |
