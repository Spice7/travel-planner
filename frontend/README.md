# 어디갈건호 프론트

## 장소 목록

`/scraps`는 전체 장소 목록을 읽기 전용으로 표시합니다. 스크랩 저장 목록은 아직 아닙니다. 데이터는 백엔드의 `GET /api/v1/places?page=&size=`에서 받고, 프론트는 DB에 직접 접속하지 않습니다.

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local`에 백엔드 주소(`API_SERVER_URL`, [`.env.example`](.env.example) 참고)를 넣고, 백엔드를 먼저 실행한 뒤 `http://localhost:3000/scraps`에서 목록을 확인하세요. 스크랩 저장 연결은 이후 작업입니다.

## 로그인

`/signup`, `/login`은 Next 라우트(`app/api/auth/*`)를 거쳐 백엔드에 가입·로그인하고, 받은 토큰을 httpOnly 쿠키(`tripfit_token`)에 담습니다. 브라우저 스크립트는 토큰을 읽지 못하며, `middleware.ts`가 `/api/v1/*` 요청에 쿠키의 토큰을 `Authorization` 헤더로 붙여 백엔드로 넘깁니다. 로그인이 필요한 `/analyzer`도 이 경로로 동작합니다.
