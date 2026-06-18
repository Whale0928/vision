# Image Persistence Plan

## 목표

이미지 업로드를 임시 파일 처리에서 영속 처리로 전환한다. 구현 순서는 이미지 전처리, PyFilesystem2 기반 파일 저장, SQLite `files` 테이블 저장 순서로 진행한다.

우선 구현 목표는 분석 결과 저장이 아니라 파일 영속성이다. 파일 입력 시 원본 bytes 기준으로 완전 동일 이미지 여부를 먼저 판단하고, 저장된 `file_id` 하나로 원본 이미지, 전처리 이미지, 썸네일, 처리 메타데이터를 확인할 수 있게 한다.

## 기준 이슈

- 기준 문서: https://github.com/bottle-note/workspace/issues/278
- 핵심 방향:
  - 원본 이미지는 보존한다.
  - 모델 입력용 이미지는 별도 규격화한다.
  - 입력 이미지는 JPEG, 1024x1365, 3:4 세로형, sRGB, 품질 90, EXIF 제거 기준으로 통일한다.
  - 라벨 잘림 방지를 위해 crop보다 contain + padding을 우선한다.

## 이미지 표준 스펙 검토

이 프로젝트의 현재 목적에는 이슈 #278의 이미지 표준을 기본값으로 채택한다.

- `JPEG`: GPT 입력과 파일 크기 관리에 유리하다. 투명 배경 이미지는 전처리 중 배경색을 채워 JPEG로 저장한다.
- `1024x1365`: 3:4 세로형에 가까운 정수 캔버스다. 병/라벨 중심 이미지에는 충분한 입력 해상도와 비용 방어 사이의 균형점이다.
- `sRGB`: 모델 입력과 브라우저 미리보기에서 색 해석을 안정화한다.
- `quality=90`: 라벨 텍스트 손상을 줄이면서 과도한 파일 크기를 피한다.
- `EXIF 제거`: 개인정보와 기기 메타데이터를 제거하고, 같은 이미지가 같은 출력 조건을 갖게 한다.
- `contain + padding`: 위스키 병 라벨은 잘림이 치명적이므로 crop보다 안전하다.

주의점:

- `1024x1365`는 수학적으로 완전한 3:4가 아니라 3:4에 가까운 실무 캔버스다.
- 작은 라벨 텍스트가 많은 이미지에서는 원본 보존이 중요하다. 모델 입력은 규격화 이미지를 쓰되, 디버깅과 재처리를 위해 원본 경로를 함께 저장한다.
- 여러 병이 있는 이미지나 가로 사진은 contain 처리 시 대상 병이 작아질 수 있다. 첫 단계에서는 감지/자동 crop을 넣지 않고, 원본과 전처리본을 함께 남겨 후속 개선 여지를 둔다.

## 저장 흐름

```text
UploadFile
  -> 원본 bytes 읽기
  -> original_sha256 계산
  -> files.original_sha256 중복 조회
     -> 이미 있으면 기존 file_id 반환 또는 분석 캐시 후보로 사용
  -> 파일 ID 생성
  -> 원본 이미지 저장
  -> Pillow 전처리
  -> 전처리 이미지 저장
  -> 썸네일 이미지 저장
  -> files 테이블에 원본/전처리 메타데이터 저장
  -> 전처리 이미지 경로로 GPT 분석
  -> 이후 analysis_runs, steps, token usage 저장으로 확장
```

사용자 흐름:

```text
1. 이미지 저장 탭에서 이미지 입력
1-1. 원본 bytes SHA-256으로 완전히 같은 이미지인지 먼저 확인
2. 이미지 유니크 키(file_id) 할당
3. 원본 이미지를 스토리지에 저장하고 files 테이블에 원본 메타데이터 저장
4. 이미지 보정
   ㄴ 사이즈 보정
   ㄴ sRGB 변환
   ㄴ EXIF 제거
   ㄴ JPEG 인코딩
   ㄴ 썸네일 생성
5. 보정 이미지와 썸네일 저장 후 files 테이블 갱신
6. 저장 목록 탭에서 썸네일 확인
7. 저장 목록에서 항목 클릭 시 이미지 상세 탭으로 이동
8. file_id로 원본, 보정 이미지, 썸네일, 처리 결과를 모두 확인
```

캐싱 기준:

- `original_sha256`: 업로드 파일이 바이트 단위로 완전히 같은지 판단한다.
- `processed_sha256`: 전처리 결과물이 같은지 판단한다.
- 분석 결과 캐시는 `processed_sha256 + model + prompt_version + schema_version + detail` 조합으로 분리한다.

## 디렉터리 구조

Docker에서는 `/data`를 volume으로 둔다.

```text
/data/
├── vision.db
└── objects/
    └── files/
        ├── original/
        │   └── 2026/06/18/<file_id>.jpg
        ├── processed/
        │   └── 2026/06/18/<file_id>.jpg
        └── thumbnails/
            └── 2026/06/18/<file_id>.jpg
```

애플리케이션 기본값:

```text
VISION_DATA_DIR=/data
```

`VISION_DATA_DIR` 아래에 `vision.db`와 `objects/`를 함께 둔다. 로컬 개발 기본값은 프로젝트 루트의 `.data/`다.

## 라이브러리

- `Pillow`: 이미지 열기, sRGB 변환, contain + padding, JPEG 저장
- `PyFilesystem2`: `/data/objects` 이하 파일 저장/조회/메타데이터 확인
- `SQLAlchemy`: SQLite 연결, `files` 테이블 저장/조회

## 전처리 정책

입력:

- JPEG, PNG, WEBP, HEIC/HEIF를 우선 지원한다.
- 지원하지 않는 포맷은 400 응답으로 거절한다.

출력:

- 포맷: JPEG
- 크기: 1024x1365
- 색공간: sRGB
- 품질: 90
- EXIF: 제거
- 배치: contain + padding
- 배경색: 흰색 `#FFFFFF`

썸네일:

- 포맷: JPEG
- 크기: 320x426
- 생성 기준: 전처리 이미지에서 contain + padding 없이 같은 비율로 축소
- 용도: 저장된 이미지 목록 미리보기

전처리 메타데이터:

```text
source_width
source_height
processed_width
processed_height
source_mime
processed_mime
source_size_bytes
processed_size_bytes
preprocess_profile
original_sha256
processed_sha256
thumbnail_object_path
thumbnail_size_bytes
```

## files 테이블 초안

처음 목표는 파일 자체의 영속성 관리다. 분석 결과, 단계 상태, 토큰, 비용은 후속 테이블로 분리한다.

```sql
CREATE TABLE files (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  original_filename TEXT,
  status TEXT NOT NULL,
  source_mime TEXT NOT NULL,
  source_size_bytes INTEGER NOT NULL,
  source_width INTEGER NOT NULL,
  source_height INTEGER NOT NULL,
  original_object_path TEXT NOT NULL,
  original_sha256 TEXT NOT NULL,
  processed_object_path TEXT NOT NULL,
  processed_sha256 TEXT NOT NULL,
  processed_mime TEXT NOT NULL,
  processed_size_bytes INTEGER NOT NULL,
  processed_width INTEGER NOT NULL,
  processed_height INTEGER NOT NULL,
  thumbnail_object_path TEXT NOT NULL,
  thumbnail_size_bytes INTEGER NOT NULL,
  preprocess_profile TEXT NOT NULL,
  original_saved_at TEXT NOT NULL,
  processed_saved_at TEXT NOT NULL
);
```

인덱스:

```sql
CREATE INDEX idx_files_created_at ON files(created_at);
CREATE UNIQUE INDEX idx_files_original_sha256 ON files(original_sha256);
CREATE INDEX idx_files_processed_sha256 ON files(processed_sha256);
```

상태값:

```text
original_saved
processed_saved
failed
```

## 화면 UX 기준

1차 카테고리:

```text
위스키 라벨 분석 | 이미지 전처리
```

`이미지 전처리` 내부 책갈피 탭:

```text
이미지 저장 | 저장 목록 | 이미지 상세
```

탭 역할:

- `이미지 저장`: 업로드, 저장 실행, 단계별 처리 로그 확인
- `저장 목록`: 저장된 이미지들을 썸네일 중심으로 확인
- `이미지 상세`: 선택한 `file_id`의 원본, 보정 이미지, 썸네일, 처리 메타데이터 확인

동작:

- `이미지 저장` 탭에는 `저장 실행`만 둔다.
- `로그 초기화` 버튼은 두지 않는다. 새 저장 실행 시 기존 로그를 자동 초기화한다.
- `저장 목록`에서 이미지 카드를 클릭하면 `이미지 상세` 탭으로 이동한다.
- `이미지 상세`는 URL 또는 내부 상태에 선택된 `file_id`를 보유해야 한다.
- 상세 진입 시 해당 `file_id`의 원본/보정/썸네일 이미지와 메타데이터를 다시 조회한다.

저장 로그 표시 기준:

```text
원본 해시 계산
  original_sha256 중복 확인
원본 저장
  objects/files/original
이미지 보정
  ㄴ 사이즈 보정
  ㄴ sRGB 변환
  ㄴ EXIF 제거
  ㄴ JPEG 인코딩
  ㄴ 썸네일 생성
보정 이미지 저장
  processed + thumbnail
DB files 갱신
  status=processed_saved
```

각 단계와 하위 단계는 `elapsed_ms`와 초 단위 표시를 함께 가진다.

## 코드 배치안

```text
app/images/
├── __init__.py
├── preprocess.py        # Pillow 전처리
└── profiles.py          # 표준 스펙 상수

app/storage/
├── __init__.py
└── object_store.py      # PyFilesystem2 저장소

app/db/
├── __init__.py
├── session.py           # SQLite engine/session
└── models.py            # files 모델

app/repositories/
├── __init__.py
└── files.py             # files insert/get

app/services/
└── file_ingestion.py    # upload -> preprocess -> storage -> DB 저장
```

## 구현 순서

### 1단계: 이미지 전처리

- `Pillow` 의존성을 추가한다.
- 전처리 프로필 상수를 만든다.
- 원본 bytes를 받아 JPEG 1024x1365와 JPEG 320x426 썸네일로 변환하는 함수를 만든다.
- RGB/sRGB 변환, contain + padding, EXIF 제거를 테스트한다.
- 원본 bytes 기준 `original_sha256`, 전처리 bytes 기준 `processed_sha256`을 계산한다.

### 2단계: PyFilesystem2 파일 저장

- `fs` 의존성을 추가한다.
- `/data/objects/files/original/...`, `/data/objects/files/processed/...`, `/data/objects/files/thumbnails/...` 경로 규칙을 만든다.
- 파일 ID와 날짜 기반 경로를 생성한다.
- 원본 bytes, 전처리 bytes, 썸네일 bytes를 저장하고 size/path를 반환한다.

### 3단계: SQLite files 테이블 저장

- `SQLAlchemy` 의존성을 추가한다.
- SQLite engine과 `files` 모델을 만든다.
- 앱 시작 시 `files` 테이블을 생성한다.
- 업로드 처리에서 원본 SHA-256 중복을 먼저 조회한다.
- 신규 이미지면 원본 저장, 전처리, 썸네일 저장 후 `files` row를 `processed_saved`로 insert한다.
- `/api/analyze`는 이 흐름으로 원본/전처리본/썸네일을 저장한 뒤 저장된 전처리 이미지 경로를 GPT 분석에 사용한다.

### 4단계: 파일 API

#### `POST /api/files`

이미지를 저장하고 전처리한다. 분석은 수행하지 않는다.

요청:

```text
multipart/form-data
image: file
```

응답:

```json
{
  "file_id": "file_01jz9m",
  "status": "processed_saved",
  "duplicate": false,
  "original_sha256": "9f42...",
  "processed_sha256": "0ab7...",
  "original_url": "/api/files/file_01jz9m/original",
  "processed_url": "/api/files/file_01jz9m/processed",
  "thumbnail_url": "/api/files/file_01jz9m/thumbnail",
  "steps": [
    {
      "label": "이미지 보정",
      "elapsed_ms": 246,
      "children": [
        {"label": "사이즈 보정", "elapsed_ms": 92},
        {"label": "sRGB 변환", "elapsed_ms": 41},
        {"label": "EXIF 제거", "elapsed_ms": 23},
        {"label": "JPEG 인코딩", "elapsed_ms": 66},
        {"label": "썸네일 생성", "elapsed_ms": 24}
      ]
    }
  ]
}
```

중복 이미지 응답:

```json
{
  "file_id": "file_01jz9m",
  "status": "processed_saved",
  "duplicate": true,
  "original_sha256": "9f42...",
  "processed_sha256": "0ab7...",
  "thumbnail_url": "/api/files/file_01jz9m/thumbnail",
  "steps": [
    {"label": "원본 해시 계산", "elapsed_ms": 5},
    {"label": "중복 이미지 확인", "elapsed_ms": 2}
  ]
}
```

#### `GET /api/files`

저장 목록 탭에서 사용한다.

쿼리:

```text
limit=40
```

응답:

```json
{
  "items": [
    {
      "file_id": "file_01jz9m",
      "created_at": "2026-06-18T13:25:01+09:00",
      "original_filename": "20260618_glena_17.jpg",
      "status": "processed_saved",
      "thumbnail_url": "/api/files/file_01jz9m/thumbnail",
      "processed_width": 1024,
      "processed_height": 1365,
      "original_sha256_short": "9f42c18a"
    }
  ],
  "next_cursor": null
}
```

#### `GET /api/files/{file_id}`

이미지 상세 탭에서 사용한다.

응답:

```json
{
  "file_id": "file_01jz9m",
  "created_at": "2026-06-18T13:25:01+09:00",
  "status": "processed_saved",
  "original_filename": "20260618_glena_17.jpg",
  "original_sha256": "9f42...",
  "processed_sha256": "0ab7...",
  "original_url": "/api/files/file_01jz9m/original",
  "processed_url": "/api/files/file_01jz9m/processed",
  "thumbnail_url": "/api/files/file_01jz9m/thumbnail",
  "source": {
    "mime": "image/jpeg",
    "size_bytes": 2841120,
    "width": 4032,
    "height": 3024
  },
  "processed": {
    "mime": "image/jpeg",
    "size_bytes": 418211,
    "width": 1024,
    "height": 1365,
    "profile": "jpeg_1024x1365_q90"
  }
}
```

#### `GET /api/files/{file_id}/original`

원본 이미지를 반환한다.

#### `GET /api/files/{file_id}/processed`

보정 이미지를 반환한다.

#### `GET /api/files/{file_id}/thumbnail`

목록 미리보기 썸네일 이미지를 반환한다.

이미지 응답 공통:

- `Content-Type`: 저장된 이미지 MIME
- `Cache-Control`: `private, max-age=3600`
- file_id가 없으면 404
- object path가 DB에는 있는데 파일이 없으면 410

## 고려해야 할 점

- 원본과 보정본은 삭제하지 않는 것을 기본으로 한다.
- 업로드 원본이 완전히 같은지 판단하는 기준은 `original_sha256`이다.
- EXIF만 다른 같은 사진은 `original_sha256`이 달라질 수 있다. 이 경우는 `processed_sha256` 또는 후속 perceptual hash로 별도 처리한다.
- SQLite unique index 충돌은 동시 업로드 중복 상황에서 정상적으로 발생할 수 있다. insert 실패 시 기존 row를 다시 조회하는 흐름이 필요하다.
- 파일 저장과 DB 저장은 하나의 트랜잭션으로 완전히 묶을 수 없다. 파일 저장 성공 후 DB 실패, DB 성공 후 파일 저장 실패 보정 전략이 필요하다.
- 실패 row는 `failed` 상태로 남기고, 실패한 단계와 에러 메시지는 후속 `file_steps` 또는 `analysis_steps` 테이블로 분리한다.
- 저장 목록은 처음부터 전체 로딩하지 않고 `limit/cursor` 페이지네이션을 사용한다.
- 썸네일은 목록 전용으로 별도 저장한다. 목록에서 원본이나 1024x1365 이미지를 직접 쓰지 않는다.
- 상세 화면의 이미지 URL은 `file_id` 기반 API만 노출하고, 실제 object path는 클라이언트에 노출하지 않는다.
- Docker에서는 `/data`를 volume으로 마운트한다. volume이 없으면 컨테이너 삭제 시 이미지와 SQLite 파일이 함께 사라진다.
- 대용량 업로드 제한이 필요하다. 1차 기준은 요청당 10MB 내외로 둔다.
- 지원 포맷은 JPEG, PNG, WEBP, HEIC/HEIF로 시작한다. HEIC/HEIF는 `pillow-heif`로 처리한다.
- 이미지 보정 단계는 상위 `이미지 보정` 총 소요 시간과 하위 단계별 소요 시간을 모두 기록한다.
- 이후 분석 결과 캐시는 `processed_sha256 + model + prompt_version + schema_version + detail` 조합으로 판단한다.

## 후속 확장

이 문서 범위 밖이지만 다음 테이블을 분리해서 추가한다.

- `analysis_runs`: 분석 요청 단위, 모델, 상태, 총 소요 시간, 결과 JSON
- `analysis_steps`: 단계별 상태, 시작/종료 시간, 에러
- `token_usages`: input/output/total token, 비용 추정
- `cost_snapshots`: 날짜/모델별 비용 시계열 집계

## 검증 기준

- 업로드 이미지가 원본과 전처리본으로 모두 저장된다.
- 업로드 이미지의 썸네일이 저장된다.
- 같은 파일을 다시 업로드하면 `original_sha256`으로 기존 파일을 식별한다.
- 전처리본은 항상 JPEG 1024x1365, 품질 90, EXIF 제거 상태다.
- `files` 테이블에 원본/전처리 object path와 이미지 메타데이터가 저장된다.
- `file_id`로 원본, 전처리본, 썸네일을 조회할 수 있다.
- 기존 `/api/analyze` 응답 구조는 유지된다.
- `uv run python -m unittest discover -s tests`가 통과한다.
