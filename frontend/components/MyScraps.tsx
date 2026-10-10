'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { compareScraps, deleteScrap } from '@/lib/api';
import type { AspectScore, Page, Scrap, ScrapRecommendation } from '@/lib/api-types';

const categoryName: Record<string, string> = { hotel: '숙소', restaurant: '식당', attraction: '관광지' };
const MIN_COMPARE = 2;

const formatDate = (iso: string) => new Date(iso).toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' });

function Factor({ title, scores }: { title: string; scores: AspectScore[] }) {
  if (!scores.length) return null;
  return <span className="why">{title}: {scores.map((s) => (
    <span key={s.aspect} className="factor">{s.label} {Math.round(s.goodness)}점{s.evidence && <> “{s.evidence}”</>}</span>
  ))}</span>;
}

export default function MyScraps({ data }: { data: Page<Scrap> }) {
  const router = useRouter();
  const [scraps, setScraps] = useState(data.items);
  const [selected, setSelected] = useState<number[]>([]);
  const [requirements, setRequirements] = useState('');
  const [result, setResult] = useState<ScrapRecommendation | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const pages = Math.max(1, Math.ceil(data.total / data.size));

  const toggle = (id: number) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const remove = async (id: number) => {
    setError('');
    try {
      await deleteScrap(id);
      setScraps((s) => s.filter((x) => x.scrap_id !== id));
      setSelected((s) => s.filter((x) => x !== id));
      setResult(null); // 지운 장소가 남은 비교 결과는 더 이상 맞지 않는다
      router.refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const compare = async (event: FormEvent) => {
    event.preventDefault();
    setError(''); setResult(null); setLoading(true);
    try { setResult(await compareScraps(selected, requirements.trim())); }
    catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  };

  return (
    <>
      <header className="appbar center">
        <Link href="/" aria-label="홈으로">←</Link>
        <h1>내 스크랩</h1>
        <span />
      </header>
      <div className="scraps">
        {!scraps.length ? (
          <p className="muted">아직 스크랩한 장소가 없어요. <Link href="/places" className="link">장소 둘러보기</Link></p>
        ) : <>
          <p className="muted">비교할 장소를 {MIN_COMPARE}곳 이상 고르고 원하는 조건을 적어 주세요.</p>
          <ul className="scrap-rows">{scraps.map((scrap) => (
            <li key={scrap.scrap_id} className="scrap-row">
              <input type="checkbox" aria-label={`${scrap.place?.name ?? scrap.title} 선택`}
                checked={selected.includes(scrap.scrap_id)} onChange={() => toggle(scrap.scrap_id)} />
              <Link href={scrap.place_id ? `/place/${scrap.place_id}` : '#'}>
                <b>{scrap.place?.name ?? scrap.title ?? `스크랩 #${scrap.scrap_id}`}</b>
                <small>{scrap.place ? `${categoryName[scrap.place.category] ?? scrap.place.category}${scrap.place.region ? ` · ${scrap.place.region}` : ''} · ` : ''}{formatDate(scrap.created_at)} 저장</small>
              </Link>
              <button type="button" onClick={() => remove(scrap.scrap_id)}>삭제</button>
            </li>
          ))}</ul>
          {pages > 1 && <div className="scrap-pagination">
            {data.page > 1 ? <Link href={`/scraps?page=${data.page - 1}`}>이전</Link> : <span />}
            <span>{data.page} / {pages}</span>
            {data.page < pages ? <Link href={`/scraps?page=${data.page + 1}`}>다음</Link> : <span />}
          </div>}
          <form className="compare-form" onSubmit={compare}>
            <textarea rows={2} maxLength={500} placeholder="예: 부모님과 가는데 계단은 피하고 바다 전망이 좋았으면 해요"
              value={requirements} onChange={(e) => setRequirements(e.target.value)} />
            <button disabled={loading || selected.length < MIN_COMPARE || !requirements.trim()}>
              {loading ? '비교하는 중…' : `비교 추천 (${selected.length}곳)`}
            </button>
          </form>
        </>}
        {error && <p role="alert" className="auth-error">{error}</p>}
        {result && <section className="bot-group">
          {!!result.weights.length && <div className="conditions">{result.weights.map((w) => <span key={w.aspect}>{w.label}</span>)}</div>}
          {!!result.ignored_keywords.length && <p className="muted">신경 쓰지 않음: {result.ignored_keywords.join(', ')}</p>}
          <p className="muted">{result.interpreter === 'model' ? '요구사항을 파인튜닝 모델로 해석했어요.' : '모델을 쓸 수 없어 키워드로 요구사항을 해석했어요.'}</p>
          {result.items.length ? <div className="results">{result.items.map((item) => (
            <Link key={item.place_id} href={`/place/${item.place_id}`} className="item">
              <span className="rank">{item.rank}</span>
              <span><b>{item.place_name ?? `장소 #${item.place_id}`}</b><span className="meta">{categoryName[item.category] ?? item.category} · 리뷰 {item.review_count}건</span></span>
              <span className="pct">{Math.round(item.fit)}<small>적합도</small></span>
              <span className="why">{item.reason}</span>
              <Factor title="강점" scores={item.strengths} />
              <Factor title="주의" scores={item.cautions} />
            </Link>
          ))}</div> : <p className="muted">비교할 수 있는 장소가 없어요.</p>}
          {result.skipped.map((s) => <p key={s.scrap_id} className="muted">{s.reason}</p>)}
        </section>}
      </div>
    </>
  );
}
