# 어디갈건호 API 명세서

Sep 29, 2026 · @Dorothy

## 개요

어디갈건호 프론트엔드(Next.js)와 FastAPI 백엔드 사이의 API 계약입니다. 프론트 타입은 `frontend/lib/api-types.ts`, DB 스키마는 `docs/db_schema.sql`에 있고, 프론트는 Mock 없이 이 API만 호출합니다.

- **Base URL**: `/api/v1` (브라우저는 Next.js의 `/api/v1/*`를 호출하고, Next.js가 FastAPI의 같은 경로로 넘깁니다)
- **형식**: 요청·응답 모두 `application/json`, UTF-8
- **필드 표기**: snake\_case (API와 프론트 타입 모두)
- **인증**: 조회 API는 인증 없이 호출 가능. 사용자·스크랩 API, 리뷰 분석(`POST /api/v1/analyze`), 스크랩 비교 추천(`POST /api/v1/recommendations`)은 `Authorization: Bearer <access_token>` 필요. 프론트는 토큰을 httpOnly 쿠키에 두고 미들웨어가 이 헤더를 붙입니다
- **ID**: DB의 BIGINT를 그대로 정수로 반환

### 공통 에러 응답

성공 시에는 리소스를 그대로 반환하고, 실패 시에는 아래 형식으로 반환합니다.

```json
{ "error": { "code": "PLACE_NOT_FOUND", "message": "장소를 찾을 수 없습니다." } }
```

| HTTP | code 예시 | 의미 |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | 필수 필드 누락, 허용되지 않은 값 (입력 검증 실패도 422가 아니라 400) |
| 401 | `UNAUTHORIZED` | 토큰 없음 또는 만료 |
| 401 | `INVALID_CREDENTIALS` | 로그인 시 이메일 또는 비밀번호 불일치 |
| 403 | `FORBIDDEN` | 다른 사용자의 리소스 접근 |
| 404 | `PLACE_NOT_FOUND`, `SCRAP_NOT_FOUND`, `METRICS_NOT_FOUND`, `NOT_FOUND` | 리소스 없음 (`NOT_FOUND`는 없는 경로) |
| 409 | `ALREADY_EXISTS` | 이메일 중복, 중복 스크랩 |
| 422 | `MODEL_OUTPUT_INVALID` | 모델 출력이 분석 형식에 맞지 않음 |
| 500 | `INTERNAL_ERROR` | 처리되지 않은 서버 오류 |
| 503 | `MODEL_UNAVAILABLE` | 분석 모델이 설정되지 않았거나 모델 서버에 연결할 수 없음 |
| 503 | `DATABASE_UNAVAILABLE` | 추천에 필요한 DB에 연결할 수 없음 |

`message`는 사용자에게 그대로 보여 줄 한국어 문장입니다. 백엔드 구현은 `backend/api/errors.py`에 있습니다.

### 목록 페이지네이션

목록 API는 `?page=1&size=20`(최대 100)을 받고 `{ "items": [...], "page": 1, "size": 20, "total": 132 }`를 반환합니다.

## 장소 API

장소 목록(`/places`)과 장소 상세(`/place/[id]`) 화면이 사용합니다. 모두 인증 없이 호출합니다.

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/places` | 장소 목록 |
| GET | `/api/v1/places/{place_id}` | 장소 상세 + 이미지·태그 |
| GET | `/api/v1/places/{place_id}/profile` | Place Review Profile(Aspect 집계) |
| GET | `/api/v1/places/{place_id}/evidence` | Aspect별 근거 리뷰 |

### GET /api/v1/places

| Query | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `category` | `hotel` \| `restaurant` \| `attraction` | 아니오 | 카테고리 필터 |
| `region` | `haeundae` \| `gwangan` \| `seomyeon` \| `wondo` \| `west` | 아니오 | 지역 코드(`regions.region_code`) |
| `q` | string | 아니오 | 장소명 부분 검색 |
| `page`, `size` | int | 아니오 | 페이지네이션 |

`category`, `region`, `q`는 **아직 구현되지 않았습니다.** 지금은 `page`, `size`만 받습니다.

응답 `200`: `Place` 목록(페이지 형식).

```json
{
  "items": [
    {
      "place_id": 12,
      "name": "감천문화마을",
      "category": "attraction",
      "region": "west",
      "district": "사하구",
      "address": "부산 사하구 감내항로 203",
      "latitude": 35.0975,
      "longitude": 129.0106,
      "summary": "사진은 좋지만 언덕·계단이 많은 마을",
      "main_image_url": "https://...",
      "review_count": 184
    }
  ],
  "page": 1, "size": 20, "total": 132
}
```

### GET /api/v1/places/{place\_id}

응답 `200`: `Place` 필드에 `images`(`image_url`, `is_main`, `sort_order`)와 `tags`(`category`, `tag_name`)가 추가됩니다. 없는 ID면 `404 PLACE_NOT_FOUND`.

### GET /api/v1/places/{place\_id}/profile

리뷰 구조화 결과(`review_annotations`)를 장소 단위로 집계한 값입니다. `share`는 해당 polarity로 언급한 리뷰 비율(%), `ratio`와 `context_satisfaction`도 %입니다.

```json
{
  "place_id": 12,
  "aspects": [
    { "aspect": "photo_spots", "polarity": "positive", "share": 82, "mentions": 97 },
    { "aspect": "walking_burden", "polarity": "negative", "share": 64, "mentions": 71 }
  ],
  "contexts": [ { "context": "couple", "ratio": 38 }, { "context": "parents", "ratio": 12 } ],
  "context_satisfaction": { "couple": 88, "parents": 54 }
}
```

### GET /api/v1/places/{place\_id}/evidence

| Query | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `aspect` | string | 예 | 예: `walking_burden` |
| `sentiment` | `positive` \| `negative` \| `neutral` | 아니오 | 감성 필터 |
| `context` | TravelerContext | 아니오 | 동행 유형 필터 |
| `limit` | int | 아니오 | 기본 5, 최대 20 |

응답 `200`: 리뷰 원문과 근거 구간. 프론트의 `[[ ]]` 표기 대신 문자 위치(`evidence_start`, `evidence_end`)를 내려줍니다.

```json
[
  {
    "review_id": 5531,
    "text": "부모님과 갔는데 언덕이 많아서 힘들었어요.",
    "context": "parents",
    "sentiment": "negative",
    "evidence_start": 9,
    "evidence_end": 23
  }
]
```

## 리뷰 분석·추천 API

리뷰 분석(`/analyzer`), 조건 추천(`/chat`), 모델 비교(`/admin/compare`) 화면이 사용합니다. `POST /api/v1/analyze`만 로그인이 필요하고(모델 GPU 보호), 나머지는 인증 없이 호출합니다.

| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/v1/analyze` | 리뷰 한 건을 모델로 구조화 |
| GET | `/api/v1/recommendations` | 사용자 조건에 맞는 장소 순위 |
| GET | `/api/v1/experiments` | Base/LoRA/QLoRA 평가 지표 |

### POST /api/v1/analyze

요청 본문 (`AnalyzeRequest`)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `review` | string | 예 | 리뷰 원문, 1\~2000자 |
| `category` | `hotel` \| `restaurant` \| `attraction` | 예 | 리뷰 대상 카테고리 |
| `model` | `base` \| `lora` \| `qlora` | 예 | 사용할 모델 |

응답 `200` (`AnalysisResult`)

```json
{
  "traveler_context": ["parents"],
  "aspects": [
    { "category": "photo_spots", "attribute": "good", "sentiment": "positive", "evidence": "사진은 정말 잘 나오지만" },
    { "category": "walking_burden", "attribute": "high", "sentiment": "negative", "evidence": "언덕이 많아서 힘들었어요" }
  ]
}
```

- `aspects[].category`는 장소 카테고리가 아니라 Aspect 이름입니다(프론트 타입 명칭을 그대로 둠).
- 허용 Aspect·Attribute 값은 `common/common/schema.py`의 `ASPECTS`, `ATTRIBUTES`를 따릅니다.
- 모델 출력이 JSON 파싱에 실패하면 `422 MODEL_OUTPUT_INVALID`, 모델이 로드되지 않았으면 `503 MODEL_UNAVAILABLE`.

### GET /api/v1/recommendations

프론트 URL 쿼리(`/recommendations?with=parents&walk=low&pri=sea,food&avoid=waiting`)를 그대로 받습니다. LLM이 장소를 고르지 않고, Place Review Profile에 조건별 가중치를 적용해 Fit 점수를 계산합니다.

| Query | 값 | 필수 |
| --- | --- | --- |
| `with` | `solo` \| `friends` \| `couple` \| `parents` \| `kids` | 아니오 |
| `walk` | `ok` \| `moderate` \| `low` | 아니오 |
| `pri` | `sea`, `food`, `photo`, `culture`, `rest`, `quiet` (쉼표 구분) | 아니오 |
| `avoid` | `waiting`, `stairs`, `noise`, `parking`, `crowd` (쉼표 구분) | 아니오 |
| `category` | `hotel` \| `restaurant` \| `attraction` | 아니오 |
| `limit` | int, 기본 10 | 아니오 |

응답 `200`: `fit` 내림차순 `FitResult` 목록. `fit`이 40 미만인 장소는 포함하지 않는다.

- 조건이 있으면 그 조건의 aspect가 리뷰에 언급된 장소만 후보가 된다. 조건이 없거나 `pri=culture`처럼 대응 aspect가 없는 조건뿐이면 리뷰 전반 만족도로 매긴다.
- `reason`은 고른 장소의 리뷰로 모델이 쓴다. 모델을 쓸 수 없으면 라벨 기반 문장으로 대신한다.
- 현재 `strengths`·`cautions`는 빈 배열로 응답한다.

```json
[
  {
    "place": { "place_id": 31, "name": "해동용궁사", "category": "attraction", "region": "haeundae" },
    "fit": 78,
    "reason": "바다 경치는 좋지만 계단이 많다는 리뷰가 있어요",
    "strengths": [ { "aspect": "scenery", "polarity": "positive", "share": 91, "weight": 5, "delta": 12 } ],
    "cautions": [ { "aspect": "slope_stairs", "polarity": "negative", "share": 58, "weight": 4, "delta": -7 } ]
  }
]
```

### GET /api/v1/experiments

응답 `200`: 평가 파이프라인(`evaluation/`)의 `automatic_metrics.json`을 화면용으로 정리한 `ExperimentMetricRow` 목록. `scores`의 키는 `base`, `lora_gold`, `qlora_gold`, `lora_gs`, `qlora_gs`입니다.

```json
[ { "metric": "Aspect F1", "unit": "f1", "scores": { "base": 0.21, "lora_gold": 0.58, "qlora_gold": 0.55, "lora_gs": 0.63, "qlora_gs": 0.61 } } ]
```

## 사용자·인증 API

`users` 테이블 기준입니다. 비밀번호는 해시(`password_hash`)로만 저장하고 응답에 포함하지 않습니다.

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/signup` | — | 회원가입 |
| POST | `/api/v1/auth/login` | — | 로그인, 토큰 발급 |
| GET | `/api/v1/users/me` | 필요 | 내 정보 |
| PATCH | `/api/v1/users/me` | 필요 | 이름·비밀번호 변경 |

### POST /api/v1/auth/signup

요청: `{ "email": "a@example.com", "password": "8자 이상", "name": "홍길동" }`

응답 `201`: `User`. 이메일이 이미 있으면 `409 ALREADY_EXISTS`.

### POST /api/v1/auth/login

요청: `{ "email": "a@example.com", "password": "..." }`

응답 `200`:

```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600, "user": { "user_id": 1, "email": "a@example.com", "name": "홍길동", "role": "member" } }
```

이메일 또는 비밀번호가 틀리면 구분 없이 `401 UNAUTHORIZED`.

### GET /api/v1/users/me, PATCH /api/v1/users/me

응답 `200`: `User`. PATCH는 `name`, `password` 중 보낸 필드만 변경하고 `updated_at`을 갱신합니다. `role`은 변경할 수 없습니다.

## 스크랩 API

`scraps`, `scrap_contents` 테이블 기준입니다. 모두 인증이 필요하며, 본인 스크랩만 조회·삭제할 수 있습니다(다른 사용자 것은 `404`).

스크랩은 담는 값에 따라 세 종류이고, 중복 규칙이 다릅니다. 같은 장소의 다른 리뷰·다른 글은 계속 저장할 수 있습니다.

| 종류 | 담는 값 | 막는 중복 (`409 ALREADY_EXISTS`) | DB 고유 인덱스 |
| --- | --- | --- | --- |
| 장소 찜 | `place_id`만 | 같은 장소를 다시 찜 ("이미 스크랩한 장소입니다.") | `ux_scraps_user_place` |
| 리뷰 저장 | `review_id` (+ 그 리뷰의 장소) | 같은 리뷰를 다시 저장 ("이미 스크랩한 리뷰입니다.") | `ux_scraps_user_review` |
| 외부 글 | `source_url` (+ 연결한 장소) | 미정 (외부 글 스크랩 단계에서 정함) | — |

| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/v1/scraps` | 스크랩 생성 |
| GET | `/api/v1/scraps` | 내 스크랩 목록 |
| GET | `/api/v1/scraps/{scrap_id}` | 스크랩 상세 + 본문 |
| PATCH | `/api/v1/scraps/{scrap_id}` | 제목 변경 |
| DELETE | `/api/v1/scraps/{scrap_id}` | 삭제(본문도 함께 삭제) |

### POST /api/v1/scraps

`place_id`, `review_id`, `source_url` 중 **최소 하나**는 있어야 합니다(DB 제약 `ck_scraps_target`). 없으면 `400 INVALID_REQUEST`.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `place_id` | int | 조건부 | 스크랩할 장소 |
| `review_id` | int | 조건부 | 스크랩할 리뷰 |
| `source_url` | string, 최대 1000자 | 조건부 | 외부 링크 |
| `title` | string, 최대 300자 | 아니오 | 표시 제목 |

- `source_type`은 서버가 정하며 요청 값은 무시합니다. `source_url`이 있으면 `external`, 없으면 `internal`입니다. `status`는 기본값 `ready`로 시작합니다.
- 리뷰 저장은 `place_id`를 비워 두면 그 리뷰의 장소로 채웁니다. 다른 장소를 지정하면 `400 INVALID_REQUEST`.
- 없는 장소·리뷰는 `404 PLACE_NOT_FOUND`·`404 REVIEW_NOT_FOUND`.

응답 `201`:

```json
{
  "scrap_id": 7,
  "user_id": 1,
  "place_id": 12,
  "review_id": null,
  "source_url": null,
  "title": "감천문화마을",
  "source_type": "internal",
  "status": "ready",
  "created_at": "2026-09-29T14:20:00",
  "updated_at": "2026-09-29T14:20:00",
  "place": { "place_id": 12, "name": "감천문화마을", "category": "attraction", "region": "west" }
}
```

`place`는 목록에서 장소를 다시 조회하지 않도록 함께 내리는 요약이며, 장소가 없는 외부 링크는 `null`입니다.

### GET /api/v1/scraps

| Query | 설명 |
| --- | --- |
| `source_type` | `internal` \| `external` 필터 |
| `place_id` | 이 장소의 스크랩만 (장소 상세에서 찜 여부 확인) |
| `page`, `size` | 페이지네이션(기본 20, 최대 100), `created_at` 최신순 |

응답 `200`: `Scrap` 목록(페이지 형식 `{ items, page, size, total }`).

### GET /api/v1/scraps/{scrap\_id}

`Scrap` 필드에 `content`가 추가됩니다. 본문이 아직 없으면 `null`입니다.

```json
"content": { "content_text": "...", "extraction_method": "html_parse", "fetched_at": "2026-09-29T14:21:03" }
```

### DELETE /api/v1/scraps/{scrap\_id}

응답 `204`. `scrap_contents`는 FK `ON DELETE CASCADE`로 함께 삭제됩니다.

### POST /api/v1/recommendations (스크랩 비교 추천)

로그인이 필요합니다. 내 스크랩의 장소들을 자연어 요구사항으로 비교해 순위를 매깁니다. 요구사항 해석에 파인튜닝 모델을 한 번 쓰고, 모델을 쓸 수 없으면 키워드 규칙으로 대신합니다(`interpreter`).

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `scrap_ids` | int[], 1~50개 | 예 | 비교할 스크랩. 같은 장소의 스크랩은 한 장소로 묶습니다 |
| `requirements` | string, 최대 500자 | 예 | 예: "부모님과 가는데 계단은 피하고 바다 전망이 좋았으면 해요" |

응답 `200`: `requirements`, `interpreter`(`model` \| `keywords`), `weights`(해석한 aspect와 가중치), `ignored_keywords`(신경 쓰지 않는다고 한 것), `items`(순위, 장소, `fit`, 이유, `strengths`·`cautions`와 근거 구절), `skipped`(장소를 알 수 없어 뺀 스크랩). 내 스크랩이 아니면 `404 SCRAP_NOT_FOUND`.

## 데이터 모델

응답 객체별 출처 테이블과 프론트 타입(`frontend/lib/api-types.ts`)의 대응입니다. 집계 객체(`PlaceProfile`, `FitResult`)는 테이블이 아니라 서버가 계산합니다.

| 응답 객체 | DB 테이블 | 프론트 타입 |
| --- | --- | --- |
| `Place` | `places` + `place_categories` + `districts` + `regions` + 대표 `place_images` | `Place` |
| `PlaceDetail` | 위 + `place_images`, `place_tags`/`tags` | `PlaceDetail` |
| `PlaceProfile` | `review_annotations` + `aspects` + `review_companions` 집계 | `PlaceProfile` |
| `EvidenceReview` | `reviews` + `review_annotations` + `companion_types` | `EvidenceReview` |
| `AnalysisResult` | 없음(모델 추론 결과) | `AnalysisResult` |
| `FitResult` | `PlaceProfile` + 요청 조건 계산 | `FitResult` |
| `ExperimentMetricRow` | 없음(`evaluation/runs/*/automatic_metrics.json`) | `ExperimentMetricRow` |
| `User` | `users` (`password_hash` 제외) | `User` |
| `Scrap` | `scraps` (+ 상세에서 `scrap_contents`, 목록에서 장소 요약) | `Scrap` |

공통 enum 값

| 이름 | 값 |
| --- | --- |
| Category | `hotel`, `restaurant`, `attraction` |
| Sentiment | `positive`, `negative`, `neutral` |
| TravelerContext | `solo`, `friends`, `couple`, `parents`, `kids`, `family` |
| ModelId | `base`, `lora`, `qlora` |
| Region | `haeundae`, `gwangan`, `seomyeon`, `wondo`, `west` |

## 미정 사항

구현 전에 팀이 정해야 할 항목입니다.

- [x] **필드 표기 통일**: 프론트 타입을 `frontend/lib/api-types.ts` 하나로 모았고 API와 같은 snake\_case를 씁니다.
- [x] **`user_scraps`와 `scraps` 중복**: `scraps`만 사용하고 `user_scraps`는 삭제했습니다(`backend/db/migrations/001_scraps_dedup.sql`).
- [x] **중복 스크랩**: 장소 찜과 리뷰 저장은 종류별로 `409`로 막습니다(스크랩 API 참고). 외부 글 규칙은 외부 글 스크랩 단계에서 정합니다.
- [x] **인증 방식**: 백엔드는 JWT Bearer입니다. 프론트는 토큰을 httpOnly 쿠키에 보관하고, Next 미들웨어가 `/api/v1/*` 요청에 `Authorization` 헤더로 붙입니다.
- [x] **분석 모델**: `/api/v1/analyze`는 Ollama 모델을 씁니다. `qlora`는 `OLLAMA_MODEL`(EXAONE 3.5 2.4B QLoRA), `base`는 `OLLAMA_MODEL_BASE`, `lora`는 `OLLAMA_MODEL_LORA`(비어 있으면 503)입니다.
- [ ] **Region 코드**: 프론의 `haeundae` 등 5개 코드가 `regions.region_code`에 같은 값으로 적재돼 있어야 합니다. 현재 DB에는 `gwangan`, `haeundae`, `wondo`, `BUSAN`만 있고 `seomyeon`, `west`가 없습니다.
- [ ] **`family` 동행 유형**: 타입에는 있지만 추천 조건 폼(`COMPANIONS`)에는 없습니다.
