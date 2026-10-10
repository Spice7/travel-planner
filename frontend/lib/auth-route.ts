import 'server-only';
import { NextResponse } from 'next/server';
import type { User } from './api-types';
import { backendUrl } from './server-api';
import { TOKEN_COOKIE } from './session';

type TokenResponse = { access_token: string; expires_in: number; user: User };
export type Credentials = { email: string; password: string; name?: string };

/** API 명세서의 공통 에러 형식으로 응답한다. 화면(lib/api.ts)은 error.message를 그대로 보여 준다. */
export function authError(status: number, code: string, message: string): NextResponse {
  return NextResponse.json({ error: { code, message } }, { status });
}

export const unavailable = () => authError(502, 'UPSTREAM_UNAVAILABLE', 'API 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.');

export async function readCredentials(request: Request, withName = false): Promise<Credentials | null> {
  const body: unknown = await request.json().catch(() => null);
  if (typeof body !== 'object' || body === null) return null;
  const { email, password, name } = body as Record<string, unknown>;
  if (typeof email !== 'string' || typeof password !== 'string') return null;
  if (withName && typeof name === 'string' && name.trim()) return { email: email.trim(), password, name: name.trim() };
  return { email: email.trim(), password };
}

/** 백엔드에 POST한다. 연결하지 못하면 null. */
export async function postBackend(path: string, body: unknown): Promise<Response | null> {
  try {
    return await fetch(backendUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
  } catch {
    return null;
  }
}

/** 백엔드에 로그인하고, 받은 토큰을 httpOnly 쿠키에 담아 응답한다. 토큰 자체는 브라우저에 내려가지 않는다. */
export async function login(credentials: Credentials): Promise<NextResponse> {
  const response = await postBackend('/auth/login', { email: credentials.email, password: credentials.password });
  if (!response) return unavailable();
  if (response.status === 401) return authError(401, 'INVALID_CREDENTIALS', '이메일 또는 비밀번호가 올바르지 않습니다.');
  if (!response.ok) return authError(400, 'INVALID_REQUEST', '이메일과 비밀번호를 확인해 주세요.');
  const token = (await response.json()) as TokenResponse;
  const result = NextResponse.json({ user: token.user });
  result.cookies.set(TOKEN_COOKIE, token.access_token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: token.expires_in,
  });
  return result;
}
