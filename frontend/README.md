# 어디갈건호 프론트

## 장소 목록

`/scraps`는 전체 장소 목록을 읽기 전용으로 표시합니다. 스크랩 저장 목록은 아직 아닙니다. 데이터는 백엔드의 `GET /api/v1/places?page=&size=`에서 받고, 프론트는 DB에 직접 접속하지 않습니다.

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local`에 백엔드 주소(`API_SERVER_URL`, [`.env.example`](.env.example) 참고)를 넣고, 백엔드를 먼저 실행한 뒤 `http://localhost:3000/scraps`에서 목록을 확인하세요. 로그인·스크랩 저장 연결은 이후 작업입니다. 메인 로그인 화면은 연결 전 표시용입니다.
