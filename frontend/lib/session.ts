// 로그인 토큰을 담는 httpOnly 쿠키. 브라우저 스크립트는 읽지 못하고, Next 서버(미들웨어·서버 컴포넌트·라우트)만 읽는다.
export const TOKEN_COOKIE = 'tripfit_token';

// 로그인 후 돌아갈 주소. 외부 주소로 보내지 않도록 같은 사이트 경로만 허용한다.
export function safeNext(raw: string | string[] | undefined): string {
  const next = Array.isArray(raw) ? raw[0] : raw;
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
}
