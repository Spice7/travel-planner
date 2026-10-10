import Link from 'next/link';
import { redirect } from 'next/navigation';
import MyScraps from '@/components/MyScraps';
import type { Page, Scrap, User } from '@/lib/api-types';
import { getMe, getMyScraps } from '@/lib/server-api';

export const dynamic = 'force-dynamic';
const PAGE_SIZE = 50;

export default async function MyScrapsPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const parsed = Number((await searchParams).page ?? '1');
  const page = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  let me: User | null;
  let data: Page<Scrap> | null = null;
  try {
    me = await getMe();
    if (me) data = await getMyScraps(page, PAGE_SIZE);
  } catch {
    return <div className="compare"><Link href="/">← 홈으로</Link><h1>내 스크랩</h1><p role="alert">스크랩을 불러오지 못했습니다. API 서버 실행 상태를 확인해 주세요.</p></div>;
  }
  if (!me || !data) redirect(`/login?next=${encodeURIComponent(page > 1 ? `/scraps?page=${page}` : '/scraps')}`);
  return <MyScraps data={data} />;
}
