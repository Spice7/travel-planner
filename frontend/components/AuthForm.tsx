'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

type Mode = 'login' | 'signup';

const TEXT = {
  login: { title: '로그인', submit: '로그인', busy: '로그인 중…', switchText: '계정이 없으신가요?', switchLink: '회원가입', switchPath: '/signup' },
  signup: { title: '회원가입', submit: '가입하기', busy: '가입 중…', switchText: '이미 계정이 있으신가요?', switchLink: '로그인', switchPath: '/login' },
} as const;

export default function AuthForm({ mode, next }: { mode: Mode; next: string }) {
  const text = TEXT[mode];
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (mode === 'signup' && password !== confirm) {
      setError('비밀번호가 서로 다릅니다.');
      return;
    }
    setError(''); setLoading(true);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mode === 'signup' ? { email, password, name } : { email, password }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setError(body?.error?.message ?? '요청에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        return;
      }
      router.replace(next);
      router.refresh();
    } catch {
      setError('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      setLoading(false);
    }
  };

  const switchHref = next === '/' ? text.switchPath : `${text.switchPath}?next=${encodeURIComponent(next)}`;
  return (
    <>
      <header className="appbar center">
        <Link href={next} aria-label="뒤로">←</Link>
        <h1>{text.title}</h1>
        <span />
      </header>
      <form className="auth" onSubmit={submit}>
        <label><span>이메일</span>
          <input type="email" autoComplete="email" required maxLength={255} value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        {mode === 'signup' && <label><span>이름 <small>선택</small></span>
          <input autoComplete="nickname" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </label>}
        <label><span>비밀번호{mode === 'signup' && <small>8자 이상</small>}</span>
          <input type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required
            minLength={mode === 'signup' ? 8 : undefined} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {mode === 'signup' && <label><span>비밀번호 확인</span>
          <input type="password" autoComplete="new-password" required maxLength={128} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </label>}
        {error && <p role="alert" className="auth-error">{error}</p>}
        <button disabled={loading}>{loading ? text.busy : text.submit}</button>
        <p className="auth-switch">{text.switchText} <Link href={switchHref}>{text.switchLink}</Link></p>
      </form>
    </>
  );
}
