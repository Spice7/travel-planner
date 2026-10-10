import { authError, login, readCredentials } from '@/lib/auth-route';

export async function POST(request: Request) {
  const credentials = await readCredentials(request);
  if (!credentials) return authError(400, 'INVALID_REQUEST', '이메일과 비밀번호를 입력해 주세요.');
  return login(credentials);
}
