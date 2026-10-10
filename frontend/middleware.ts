import { NextResponse, type NextRequest } from 'next/server';
import { TOKEN_COOKIE } from '@/lib/session';

// 브라우저는 토큰을 모르므로, /api/v1 요청을 백엔드로 넘기기 전에 쿠키의 토큰을 Authorization 헤더로 붙인다.
export function middleware(request: NextRequest) {
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (!token || request.headers.has('authorization')) return NextResponse.next();
  const headers = new Headers(request.headers);
  headers.set('authorization', `Bearer ${token}`);
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: '/api/v1/:path*' };
