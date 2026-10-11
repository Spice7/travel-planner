import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';
import ScrapReview from '@/components/ScrapReview';
import { ApiError } from '@/lib/api';
import type { ScrapDetail } from '@/lib/api-types';
import { getScrapDetail } from '@/lib/server-api';

export const dynamic = 'force-dynamic';

export default async function ScrapPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id) || !Number.isSafeInteger(Number(id))) notFound();
  let scrap: ScrapDetail;
  try {
    scrap = await getScrapDetail(Number(id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) redirect(`/login?next=/scraps/${id}`);
    if (error instanceof ApiError && error.status === 404) notFound();
    return <div className="compare"><Link href="/scraps">← 내 스크랩</Link><h1>스크랩을 불러오지 못했습니다.</h1><p role="alert">{(error as Error).message}</p></div>;
  }
  // 장소 찜은 볼 본문이 없어 장소 상세로 보낸다.
  if (scrap.source_type !== 'external' && scrap.place_id) redirect(`/place/${scrap.place_id}`);
  return <ScrapReview initial={scrap} />;
}
