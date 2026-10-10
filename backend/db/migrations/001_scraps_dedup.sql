-- 스크랩 1단계: 종류별 중복 방지와 쓰지 않는 user_scraps 삭제.
-- 적용: psql -h localhost -U <user> -d postDB -v ON_ERROR_STOP=1 -f backend/db/migrations/001_scraps_dedup.sql
-- 같은 장소의 다른 리뷰·외부 글은 계속 저장할 수 있다. 외부 글 중복 규칙은 2단계에서 정한다.

BEGIN;

-- 백엔드는 scraps만 쓴다. user_scraps는 장소만 저장하던 초기 설계의 흔적이다.
DROP TABLE IF EXISTS public.user_scraps;

-- 장소 찜: 같은 사용자가 같은 장소를 두 번 찜하지 못한다.
CREATE UNIQUE INDEX IF NOT EXISTS ux_scraps_user_place
    ON public.scraps (user_id, place_id)
    WHERE review_id IS NULL AND source_url IS NULL;

-- 리뷰 저장: 같은 사용자가 같은 리뷰를 두 번 저장하지 못한다.
CREATE UNIQUE INDEX IF NOT EXISTS ux_scraps_user_review
    ON public.scraps (user_id, review_id)
    WHERE review_id IS NOT NULL;

COMMIT;
