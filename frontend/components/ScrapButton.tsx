'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ApiError, createPlaceScrap, deleteScrap, getScrapsForPlace, isPlaceScrap } from '@/lib/api';

type Props = { placeId: number; placeName: string | null; loggedIn: boolean; initialScrapId: number | null };

// 장소 상세 하단의 찜 버튼. 상태는 서버에서 미리 받아 와서 처음부터 맞게 보인다.
export default function ScrapButton({ placeId, placeName, loggedIn, initialScrapId }: Props) {
  const [scrapId, setScrapId] = useState(initialScrapId);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!loggedIn) {
    return <div className="cta"><Link href={`/login?next=/place/${placeId}`}>로그인하고 스크랩하기</Link></div>;
  }

  const toggle = async () => {
    setBusy(true); setError('');
    try {
      if (scrapId !== null) {
        await deleteScrap(scrapId);
        setScrapId(null);
      } else {
        setScrapId((await createPlaceScrap(placeId, placeName)).scrap_id);
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ALREADY_EXISTS') {
        // 다른 탭에서 이미 찜한 경우: 그 스크랩을 찾아 상태만 맞춘다.
        const { items } = await getScrapsForPlace(placeId).catch(() => ({ items: [] }));
        setScrapId(items.find(isPlaceScrap)?.scrap_id ?? null);
      } else {
        setError((e as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cta">
      {error && <p role="alert" className="auth-error">{error}</p>}
      <button type="button" className={scrapId !== null ? 'on' : undefined} aria-pressed={scrapId !== null} disabled={busy} onClick={toggle}>
        {scrapId !== null ? '스크랩됨 ✓' : '스크랩'}
      </button>
    </div>
  );
}
