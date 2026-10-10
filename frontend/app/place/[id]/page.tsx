import { notFound } from 'next/navigation';
import { getMe, getPlaceDetail, getPlaceProfile, getPlaceScrapId } from '@/lib/server-api';
import { ApiError } from '@/lib/api';
import PlaceDetail from '@/components/PlaceDetail';

export const dynamic = 'force-dynamic';

export default async function PlacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^\d+$/.test(id) || !Number.isSafeInteger(Number(id))) notFound();
  try {
    const [place, profile, me] = await Promise.all([getPlaceDetail(Number(id)), getPlaceProfile(Number(id)), getMe().catch(() => null)]);
    // 찜 여부를 몰라도 장소 정보는 보여 준다.
    const scrapId = me ? await getPlaceScrapId(place.place_id).catch(() => null) : null;
    return <PlaceDetail place={place} profile={profile} scrap={{ loggedIn: me !== null, scrapId }} />;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <div className="compare"><h1>장소 정보를 불러오지 못했습니다.</h1><p role="alert">{(error as Error).message}</p></div>;
  }
}
