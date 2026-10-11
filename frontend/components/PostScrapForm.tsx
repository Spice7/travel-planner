'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createPostScrap, findPlaceCandidates, searchPlaces } from '@/lib/api';
import type { PlaceCandidate } from '@/lib/api-types';

const MAX_CHARS = 5000;
const MIN_CHARS = 20;
const categoryName: Record<string, string> = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };
type Choice = { place_id: number; name: string | null; category: string; hits?: number };

// 글 스크랩: 본문 붙여 넣기 → 장소 고르기 → 분석. 링크로 글을 가져오지는 않는다(원문 주소는 출처로만 저장).
export default function PostScrapForm() {
  const router = useRouter();
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [notice, setNotice] = useState('');
  const [candidates, setCandidates] = useState<Choice[] | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Choice[]>([]);
  const [chosen, setChosen] = useState<Choice | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<'' | 'find' | 'search' | 'analyze'>('');

  const changeText = (value: string) => {
    // 본문 칸에 링크만 넣으면 출처 칸으로 옮기고 본문을 붙여 넣도록 안내한다.
    if (/^https?:\/\/\S+$/.test(value.trim())) {
      setSourceUrl(value.trim()); setText('');
      setNotice('지금은 링크로 글을 가져오지 않아요. 링크는 원문 주소 칸으로 옮겼으니, 글 본문을 복사해 붙여 넣어 주세요.');
      return;
    }
    setNotice(''); setText(value); setCandidates(null); setChosen(null);
  };
  const run = async <T,>(step: 'find' | 'search' | 'analyze', job: () => Promise<T>): Promise<T | undefined> => {
    setBusy(step); setError('');
    try { return await job(); } catch (e) { setError((e as Error).message); return undefined; } finally { setBusy(''); }
  };
  const find = () => run('find', async () => {
    const found: PlaceCandidate[] = await findPlaceCandidates(text);
    setCandidates(found);
    if (found.length) setChosen(found[0]);
  });
  const search = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) void run('search', async () => setResults((await searchPlaces(query.trim())).items));
  };
  const analyze = () => chosen && run('analyze', async () => {
    const scrap = await createPostScrap({ text, place_id: chosen.place_id, title: title.trim() || null, source_url: sourceUrl.trim() || null });
    router.push(`/scraps/${scrap.scrap_id}`);
  });

  const option = (place: Choice) => (
    <li key={place.place_id} className="scrap-row">
      <input type="radio" name="place" aria-label={`${place.name} 선택`} checked={chosen?.place_id === place.place_id} onChange={() => setChosen(place)} />
      <span><b>{place.name ?? `장소 #${place.place_id}`}</b>
        <small>{categoryName[place.category] ?? place.category}{place.hits ? ` · 글에 ${place.hits}번 나옴` : ''}</small></span>
      <span />
    </li>
  );

  return (
    <>
      <header className="appbar center">
        <Link href="/scraps" aria-label="내 스크랩으로">←</Link>
        <h1>글 스크랩</h1>
        <span />
      </header>
      <div className="auth">
        <label><span>본문 <small>{text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}자</small></span>
          <textarea rows={9} maxLength={MAX_CHARS} value={text} placeholder="블로그·리뷰 글의 본문을 복사해 붙여 넣어 주세요."
            onChange={(e) => changeText(e.target.value)} />
        </label>
        {notice && <p className="notice">{notice}</p>}
        <label><span>제목 <small>선택</small></span>
          <input maxLength={300} value={title} placeholder="비우면 본문 첫 줄을 씁니다" onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label><span>원문 주소 <small>선택, 출처로만 저장</small></span>
          <input type="url" maxLength={1000} value={sourceUrl} placeholder="https://" onChange={(e) => setSourceUrl(e.target.value)} />
        </label>

        <button type="button" disabled={text.trim().length < MIN_CHARS || busy !== ''} onClick={find}>
          {busy === 'find' ? '장소 찾는 중…' : '글에 나온 장소 찾기'}
        </button>
        {candidates && <section className="post-step">
          <h2>어느 장소의 글인가요?</h2>
          <p className="muted">여러 장소가 나오는 글은 장소마다 따로 저장하세요. 고른 장소에 대한 단락만 분석합니다.</p>
          {candidates.length ? <ul className="scrap-rows">{candidates.map(option)}</ul> : <p className="muted">글에서 장소 이름을 찾지 못했어요. 아래에서 검색해 주세요.</p>}
          <form className="post-search" onSubmit={search}>
            <input value={query} maxLength={100} placeholder="장소 이름 검색" onChange={(e) => setQuery(e.target.value)} />
            <button disabled={!query.trim() || busy !== ''}>{busy === 'search' ? '검색 중…' : '검색'}</button>
          </form>
          {!!results.length && <ul className="scrap-rows">{results.map(option)}</ul>}
        </section>}

        {error && <p role="alert" className="auth-error">{error}</p>}
        {candidates && <button type="button" disabled={!chosen || busy !== ''} onClick={analyze}>
          {busy === 'analyze' ? '분석하는 중… (10초 정도 걸려요)' : chosen ? `‘${chosen.name}’ 장소로 분석하기` : '장소를 골라 주세요'}
        </button>}
      </div>
    </>
  );
}
