-- TripFit review extraction database.
-- The canonical datasets JSONL stays unchanged; each raw record is retained in reviews.raw_record.

CREATE TABLE regions (
    region_id BIGSERIAL PRIMARY KEY,
    region_code VARCHAR(20) NOT NULL UNIQUE,
    region_name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE districts (
    district_id BIGSERIAL PRIMARY KEY,
    region_id BIGINT NOT NULL REFERENCES regions(region_id) ON DELETE RESTRICT,
    district_name VARCHAR(100) NOT NULL,
    description TEXT,
    UNIQUE (region_id, district_name)
);

CREATE TABLE place_categories (
    category_id BIGSERIAL PRIMARY KEY,
    category_code VARCHAR(30) NOT NULL UNIQUE,
    category_name VARCHAR(50) NOT NULL UNIQUE,
    type VARCHAR(20)  -- 영문 표시 이름 (예: Tourist Attraction)
);

CREATE TABLE places (
    place_id BIGSERIAL PRIMARY KEY,
    category_id BIGINT NOT NULL REFERENCES place_categories(category_id) ON DELETE RESTRICT,
    district_id BIGINT REFERENCES districts(district_id) ON DELETE RESTRICT,
    source VARCHAR(50) NOT NULL,
    source_place_id VARCHAR(200) NOT NULL,
    place_name VARCHAR(200),
    address VARCHAR(500),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    intro_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id BIGINT,  -- 장소를 등록한 사용자. FK는 users 정의 뒤에 둔다
    parking_available BOOLEAN,
    UNIQUE (source, source_place_id)
);

CREATE TABLE place_images (
    image_id BIGSERIAL PRIMARY KEY,
    place_id BIGINT NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    image_url VARCHAR(1000) NOT NULL,
    is_main BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tags (
    tag_id BIGSERIAL PRIMARY KEY,
    category VARCHAR(50),
    tag_name VARCHAR(100) NOT NULL,
    UNIQUE NULLS NOT DISTINCT (category, tag_name)
);

CREATE TABLE place_tags (
    place_id BIGINT NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (place_id, tag_id)
);

CREATE TABLE companion_types (
    companion_type_id BIGSERIAL PRIMARY KEY,
    companion_code VARCHAR(50) NOT NULL UNIQUE,
    companion_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE aspects (
    aspect_id BIGSERIAL PRIMARY KEY,
    category_id BIGINT NOT NULL REFERENCES place_categories(category_id) ON DELETE CASCADE,
    aspect_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (category_id, aspect_name)
);

CREATE TABLE aspect_values (
    value_id BIGSERIAL PRIMARY KEY,
    aspect_id BIGINT NOT NULL REFERENCES aspects(aspect_id) ON DELETE CASCADE,
    value_name VARCHAR(100) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    UNIQUE (aspect_id, value_name)
);

CREATE TABLE reviews (
    review_id BIGSERIAL PRIMARY KEY,
    place_id BIGINT NOT NULL REFERENCES places(place_id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    external_review_id VARCHAR(200) NOT NULL,
    source_member VARCHAR(50),
    -- 학습 데이터셋 리뷰만 값이 있고, 서비스용 실제 리뷰는 NULL이다.
    dataset_split VARCHAR(20) CHECK (dataset_split IN ('train', 'val', 'test')),
    label_tier VARCHAR(20) CHECK (label_tier IN ('gold', 'silver')),
    is_synthetic BOOLEAN NOT NULL,
    review_text TEXT NOT NULL,
    raw_record JSONB NOT NULL,
    crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 원본 리뷰 사이트의 정보 (작성자, 평점, 방문일, 작성일)
    author_name VARCHAR(100),
    rating NUMERIC(2, 1),
    visit_date DATE,
    review_created_at TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (source, external_review_id)
);

CREATE TABLE review_annotations (
    annotation_id BIGSERIAL PRIMARY KEY,
    review_id BIGINT NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    aspect_id BIGINT NOT NULL REFERENCES aspects(aspect_id) ON DELETE RESTRICT,
    attribute_value VARCHAR(100) NOT NULL,
    sentiment VARCHAR(10) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    evidence_text TEXT NOT NULL,
    evidence_start INTEGER NOT NULL,
    evidence_end INTEGER NOT NULL,
    annotation_tier VARCHAR(20) NOT NULL CHECK (annotation_tier IN ('gold', 'silver', 'model')),
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    annotator_type VARCHAR(10),  -- 라벨을 붙인 주체 (예: model)
    CHECK (evidence_start >= 0 AND evidence_end > evidence_start),
    UNIQUE (review_id, aspect_id, attribute_value, sentiment, evidence_text)
);

CREATE TABLE review_companions (
    review_id BIGINT NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    companion_type_id BIGINT NOT NULL REFERENCES companion_types(companion_type_id) ON DELETE CASCADE,
    PRIMARY KEY (review_id, companion_type_id)
);

CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE places ADD CONSTRAINT places_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL;

CREATE TABLE scraps (
    scrap_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    place_id BIGINT,
    review_id BIGINT,
    source_url VARCHAR(1000),
    title VARCHAR(300),
    source_type VARCHAR(30) NOT NULL DEFAULT 'internal',
    status VARCHAR(20) NOT NULL DEFAULT 'ready',  -- 찜·리뷰 저장: ready / 글 스크랩: analyzed → confirmed, failed
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    content_hash VARCHAR(64),  -- 글 스크랩만: 공백을 정리한 본문의 sha256
    CONSTRAINT fk_scraps_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_scraps_place FOREIGN KEY (place_id) REFERENCES places(place_id) ON DELETE SET NULL,
    CONSTRAINT fk_scraps_review FOREIGN KEY (review_id) REFERENCES reviews(review_id) ON DELETE SET NULL,
    CONSTRAINT ck_scraps_target CHECK (place_id IS NOT NULL OR review_id IS NOT NULL OR source_url IS NOT NULL)
);

CREATE TABLE scrap_contents (
    scrap_id BIGINT PRIMARY KEY,
    content_text TEXT,
    extraction_method VARCHAR(30),
    fetched_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    promo_signals JSONB NOT NULL DEFAULT '[]',  -- 본문에서 찾은 홍보 문구
    traveler_context JSONB NOT NULL DEFAULT '[]',
    CONSTRAINT fk_scrap_contents_scrap FOREIGN KEY (scrap_id) REFERENCES scraps(scrap_id) ON DELETE CASCADE
);

-- 글 스크랩에서 모델이 뽑은 라벨. 확정(confirmed)한 것만 그 사용자의 비교 추천에 쓰고, 제외(rejected)도 남긴다.
CREATE TABLE scrap_annotations (
    annotation_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    scrap_id BIGINT NOT NULL REFERENCES scraps(scrap_id) ON DELETE CASCADE,
    aspect_id BIGINT NOT NULL REFERENCES aspects(aspect_id) ON DELETE RESTRICT,
    attribute_value VARCHAR(100) NOT NULL,
    sentiment VARCHAR(10) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    evidence_text TEXT NOT NULL,
    evidence_start INTEGER NOT NULL,
    evidence_end INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested', 'confirmed', 'rejected')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (evidence_start >= 0 AND evidence_end > evidence_start)
);

CREATE TABLE dataset_imports (
    import_id BIGSERIAL PRIMARY KEY,
    dataset_name VARCHAR(100) NOT NULL,
    manifest JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    review_count INTEGER NOT NULL,
    annotation_count INTEGER NOT NULL
);

CREATE INDEX idx_places_category ON places(category_id);
CREATE INDEX idx_places_district ON places(district_id);
CREATE INDEX idx_reviews_place ON reviews(place_id);
CREATE INDEX idx_reviews_split_tier ON reviews(dataset_split, label_tier);
CREATE INDEX idx_annotations_review ON review_annotations(review_id);
CREATE INDEX idx_annotations_aspect ON review_annotations(aspect_id);
CREATE INDEX idx_review_companions_review ON review_companions(review_id);
CREATE INDEX idx_scraps_user_id ON scraps(user_id);
CREATE INDEX idx_scraps_place_id ON scraps(place_id);
CREATE INDEX idx_scraps_review_id ON scraps(review_id);
CREATE INDEX idx_scraps_created_at ON scraps(created_at);
-- 종류별 중복 방지 (backend/db/migrations/001_scraps_dedup.sql, 002_scrap_posts.sql)
CREATE UNIQUE INDEX ux_scraps_user_place ON scraps(user_id, place_id) WHERE source_type = 'internal' AND review_id IS NULL;
CREATE UNIQUE INDEX ux_scraps_user_review ON scraps(user_id, review_id) WHERE review_id IS NOT NULL;
CREATE UNIQUE INDEX ux_scraps_user_place_content ON scraps(user_id, place_id, content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX idx_scrap_annotations_scrap ON scrap_annotations(scrap_id);
