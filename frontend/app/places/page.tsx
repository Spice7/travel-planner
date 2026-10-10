import Link from 'next/link';
import type { Page, Place } from '@/lib/api-types';
import { getPlaces } from '@/lib/server-api';

export const dynamic = 'force-dynamic';
const PAGE_SIZE = 20;
const categoryName: Record<string, string> = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };

export default async function PlacesPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const raw = (await searchParams).page;
  const parsed = Number(raw ?? '1');
  const page = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  let data: Page<Place>;
  try { data = await getPlaces(page, PAGE_SIZE); }
  catch { return <div className="compare"><Link href="/">← 홈으로</Link><h1>장소 목록</h1><p role="alert">장소 목록을 불러오지 못했습니다. API 서버 실행 상태를 확인해 주세요.</p></div>; }
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  return <div className="compare">
    <Link href="/">← 홈으로</Link>
    <h1>장소 목록</h1>
    <p className="muted">전체 {data.total}곳 · 장소를 눌러 상세에서 스크랩할 수 있어요.</p>
    {data.items.length ? <div className="scrap-list">{data.items.map((place) => (
      <Link key={place.place_id} href={`/place/${place.place_id}`} className="scrap-card">
        <b>{place.name || `장소 #${place.place_id}`}</b>
        <small>{categoryName[place.category] ?? place.category} · 리뷰 {place.review_count}건</small>
        {place.district ? <small>{place.district}</small> : null}
      </Link>
    ))}</div> : <p>표시할 장소가 없습니다.</p>}
    <div className="scrap-pagination">
      {page > 1 ? <Link href={`/places?page=${page - 1}`}>이전</Link> : <span />}
      <span>{page} / {pages}</span>
      {page < pages ? <Link href={`/places?page=${page + 1}`}>다음</Link> : <span />}
    </div>
  </div>;
}
