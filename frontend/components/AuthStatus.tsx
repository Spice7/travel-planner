import Link from 'next/link';
import { getMe } from '@/lib/server-api';
import LogoutButton from './LogoutButton';

// 홈 오른쪽 위의 로그인 상태. 백엔드에 닿지 못해도 홈은 그대로 보여 준다.
export default async function AuthStatus() {
  const user = await getMe().catch(() => null);
  return <nav className="auth-nav">
    {user
      ? <><Link href="/scraps">내 스크랩</Link><span>{user.name || user.email}님</span><LogoutButton /></>
      : <Link href="/login">로그인</Link>}
  </nav>;
}
