# Whisky Vision Pilot

위스키 병 이미지를 업로드하면 GPT Vision으로 라벨을 분석하고, 제품 식별 결과와 단계별 처리 시간을 보여주는 FastAPI 기반 파일럿입니다.

## 주요 기능

- 이미지 업로드 기반 위스키 라벨 분석
- OpenAI Responses API Structured Outputs 사용
- 식별 결과, 스펙 필드, 원문 라벨 텍스트 표시
- 업로드, 이미지 전처리, 프롬프트 구성, GPT 분석, 결과 파싱 단계별 소요 시간 표시
- 이미지 원본, 전처리본, 썸네일을 로컬 SQLite와 PyFilesystem2 저장소에 저장
- 저장 이미지 목록과 상세 확인용 전처리 화면 제공
- 로컬 폰트 기반 웹 UI 제공

## 실행 준비

Python 3.12 이상과 `uv`가 필요합니다.

```bash
uv sync
```

프로젝트 루트에 `.env` 파일을 만들고 API 키를 설정합니다.

```bash
GPT_API_KEY=your_api_key_here
```

## 실행

```bash
uv run python main.py
```

브라우저에서 다음 주소로 접속합니다.

```text
http://127.0.0.1:8080
```

이미지 전처리 확인 화면은 다음 주소로 접속합니다.

```text
http://127.0.0.1:8080/image-preprocess
```

개발 중 자동 리로드가 필요하면 다음 명령을 사용할 수 있습니다.

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

## API

### `POST /api/analyze`

`multipart/form-data`로 이미지를 업로드합니다.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `image` | file | 예 | 분석할 병 이미지 |
| `model` | string | 아니오 | 기본값 `gpt-4o-mini` |

업로드 이미지는 먼저 로컬 저장소에 원본/전처리본/썸네일로 저장되고, GPT 분석에는 전처리본 JPEG가 사용됩니다.

응답 구조는 다음과 같습니다.

```json
{
  "model": "gpt-4o-mini",
  "result": {
    "is_whisky": true,
    "identification": "이 위스키는 ...",
    "identification_reason": "라벨의 ... 단서로 식별했다."
  },
  "debug_steps": [
    {"label": "이미지 업로드", "elapsed_ms": 1},
    {"label": "이미지 전처리", "elapsed_ms": 35},
    {"label": "프롬프트 구성", "elapsed_ms": 0},
    {"label": "GPT 분석", "elapsed_ms": 1200},
    {"label": "결과 파싱", "elapsed_ms": 0}
  ],
  "total_ms": 1201
}
```

실제 `result` 필드는 [ai/response_schema.json](ai/response_schema.json)을 따릅니다.

### `POST /api/analyze/stream`

분석 화면에서 사용하는 NDJSON 스트리밍 엔드포인트입니다. 요청 필드는 `/api/analyze`와 같고, 처리 단계가 끝날 때마다 한 줄씩 이벤트를 반환합니다.

```json
{"type":"step","step":{"label":"이미지 전처리","elapsed_ms":35}}
{"type":"result","payload":{"model":"gpt-4o-mini","result":{},"debug_steps":[],"total_ms":1201}}
```

### `POST /api/files`

이미지를 저장하고 전처리합니다. GPT 분석은 수행하지 않습니다.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `image` | file | 예 | 저장할 원본 이미지 |

응답에는 `file_id`, 중복 여부, 원본/전처리 SHA-256, 이미지 조회 URL, 단계별 처리 시간이 포함됩니다.

### `GET /api/files`

저장된 이미지 목록을 반환합니다. `limit` 쿼리 파라미터를 지원합니다.

### `GET /api/files/{file_id}`

원본/전처리 메타데이터와 이미지 조회 URL을 반환합니다.

### `GET /api/files/{file_id}/{kind}`

`kind`는 `original`, `processed`, `thumbnail` 중 하나입니다.

## 프로젝트 구조

```text
.
├── ai/
│   ├── prompt.txt
│   └── response_schema.json
├── app/
│   ├── api/
│   ├── db/
│   ├── images/
│   ├── repositories/
│   ├── services/
│   ├── storage/
│   ├── static/
│   │   ├── css/
│   │   ├── fonts/
│   │   └── js/
│   ├── templates/
│   ├── main.py
│   └── schemas.py
├── analysis.py
├── config.py
├── gpt_client.py
├── main.py
└── tests/
```

## 주요 파일

- [main.py](main.py): 로깅 설정 후 Uvicorn 서버 실행
- [app/main.py](app/main.py): FastAPI 앱 생성, 정적 파일과 API 라우터 등록
- [app/api/routes.py](app/api/routes.py): `/api/analyze`, `/api/files` 엔드포인트
- [app/services/analyzer.py](app/services/analyzer.py): 업로드 파일 임시 저장, 분석 실행, 디버그 단계 기록
- [app/services/file_ingestion.py](app/services/file_ingestion.py): 이미지 저장, 전처리, DB row 생성
- [app/images/preprocess.py](app/images/preprocess.py): Pillow 기반 이미지 전처리
- [app/storage/object_store.py](app/storage/object_store.py): PyFilesystem2 기반 object 저장소
- [app/db/models.py](app/db/models.py): SQLite `files` 테이블 모델
- [analysis.py](analysis.py): GPT Vision 호출과 Structured Outputs 파싱
- [ai/prompt.txt](ai/prompt.txt): 라벨 분석 프롬프트
- [ai/response_schema.json](ai/response_schema.json): 분석 결과 JSON 스키마

## 리소스 관리

`resource/`는 샘플 이미지와 출력물 같은 로컬 리소스용 디렉터리입니다. 대용량 파일이나 개인 데이터가 섞일 수 있어 git에 올리지 않습니다.

권장 로컬 구조:

```text
resource/
├── image/
└── output/
```

UI에서 사용하는 폰트는 `app/static/fonts/`에 포함되어 있으며, CDN을 사용하지 않습니다.

## 로컬 저장소

기본 저장 위치는 프로젝트 루트의 `.data/`입니다.

```text
.data/
├── vision.db
└── objects/
    └── files/
        ├── original/
        ├── processed/
        └── thumbnails/
```

Docker에서는 볼륨을 `/data`에 마운트하고 다음 환경변수를 사용하면 됩니다.

```bash
VISION_DATA_DIR=/data
```

## 테스트

```bash
uv run python -m unittest discover -s tests
```

테스트는 FastAPI 앱 생성, 정적 폰트 서빙, 이미지 분석 API 응답 구조, 이미지 전처리, SQLite/PyFilesystem2 저장 API를 확인합니다.
