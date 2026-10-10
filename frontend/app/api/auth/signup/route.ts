import { authError, login, postBackend, readCredentials, unavailable } from '@/lib/auth-route';

// 가입에 성공하면 바로 로그인까지 해서 쿠키를 심는다.
export async function POST(request: Request) {
  const credentials = await readCredentials(request, true);
  if (!credentials) return authError(400, 'INVALID_REQUEST', '이메일과 비밀번호를 입력해 주세요.');
  const response = await postBackend('/auth/signup', credentials);
  if (!response) return unavailable();
  if (response.status === 409) return authError(409, 'ALREADY_EXISTS', '이미 가입된 이메일입니다.');
  if (!response.ok) return authError(400, 'INVALID_REQUEST', '이메일 형식과 비밀번호(8자 이상)를 확인해 주세요.');
  return login(credentials);
}
