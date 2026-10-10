# 어디갈건호 프론트

## 장소 목록과 스크랩

- `/places`: 전체 장소 목록입니다. 장소를 누르면 상세(`/place/{id}`)로 이동합니다.
- `/place/{id}`: 하단 버튼으로 장소를 스크랩(찜)하거나 취소합니다. 로그인하지 않았으면 로그인 화면으로 보냅니다.
- `/scraps`: 내 스크랩 목록입니다(로그인 필요). 2곳 이상 고르고 요구사항을 적으면 `POST /api/v1/recommendations`로 비교 추천을 받습니다. 비교 한 번에 파인튜닝 모델을 한 번 씁니다.

데이터는 모두 백엔드 `/api/v1`에서 받고, 프론트는 DB에 직접 접속하지 않습니다.

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local`에 백엔드 주소(`API_SERVER_URL`, [`.env.example`](.env.example) 참고)를 넣고, 백엔드를 먼저 실행한 뒤 `http://localhost:3000`을 여세요. 외부 글 스크랩은 이후 작업입니다.

## 로그인

`/signup`, `/login`은 Next 라우트(`app/api/auth/*`)를 거쳐 백엔드에 가입·로그인하고, 받은 토큰을 httpOnly 쿠키(`tripfit_token`)에 담습니다. 브라우저 스크립트는 토큰을 읽지 못하며, `middleware.ts`가 `/api/v1/*` 요청에 쿠키의 토큰을 `Authorization` 헤더로 붙여 백엔드로 넘깁니다. 로그인이 필요한 `/analyzer`도 이 경로로 동작합니다.
