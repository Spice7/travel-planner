'use client';

import { useState, type ReactNode } from 'react';
import Link from 'next/link';
import { confirmScrapLabels, reanalyzeScrap } from '@/lib/api';
import type { ScrapAnnotation, ScrapDetail } from '@/lib/api-types';

const sentimentName: Record<string, string> = { positive: '긍정', negative: '부정', neutral: '중립' };
const statusName: Record<string, string> = { analyzed: '확인이 필요해요', confirmed: '확정했어요', failed: '분석하지 못했어요' };

const initialChecks = (labels: ScrapAnnotation[]) => new Set(labels.filter((a) => a.status !== 'rejected').map((a) => a.annotation_id));

/** 체크한 라벨의 근거 구절을 본문에서 강조한다. 겹치는 구간은 앞의 것만. */
function highlight(text: string, labels: ScrapAnnotation[]): ReactNode[] {
  const parts: ReactNode[] = [];
  let cursor = 0;
  for (const a of [...labels].sort((x, y) => x.evidence_start - y.evidence_start)) {
    if (a.evidence_start < cursor) continue;
    parts.push(text.slice(cursor, a.evidence_start), <mark key={a.annotation_id}>{text.slice(a.evidence_start, a.evidence_end)}</mark>);
    cursor = a.evidence_end;
  }
  parts.push(text.slice(cursor));
  return parts;
}

// 글 스크랩 확인: 모델이 뽑은 라벨 중 맞는 것만 남겨 확정한다. 확정한 라벨만 내 비교 추천에 쓰인다.
export default function ScrapReview({ initial }: { initial: ScrapDetail }) {
  const [scrap, setScrap] = useState(initial);
  const [checked, setChecked] = useState(() => initialChecks(initial.annotations));
  const [busy, setBusy] = useState<'' | 'confirm' | 'analyze'>('');
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const content = scrap.content?.content_text ?? '';
  const promo = scrap.content?.promo_signals ?? [];

  const apply = (next: ScrapDetail) => { setScrap(next); setChecked(initialChecks(next.annotations)); };
  const toggle = (id: number) => { setSaved(false); setChecked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; }); };
  const run = async (step: 'confirm' | 'analyze', job: () => Promise<ScrapDetail>) => {
    setBusy(step); setError(''); setSaved(false);
    try { apply(await job()); if (step === 'confirm') setSaved(true); } catch (e) { setError((e as Error).message); } finally { setBusy(''); }
  };
  const reanalyze = () => {
    if (scrap.annotations.length && !window.confirm('다시 분석하면 지금 라벨(확정한 것 포함)이 새 제안으로 바뀝니다. 계속할까요?')) return;
    void run('analyze', () => reanalyzeScrap(scrap.scrap_id));
  };

  return (
    <>
      <header className="appbar center">
        <Link href="/scraps" aria-label="내 스크랩으로">←</Link>
        <h1>{scrap.title ?? '글 스크랩'}</h1>
        <span />
      </header>
      <div className="scraps">
        <p className="muted">
          {scrap.place ? <Link href={`/place/${scrap.place.place_id}`} className="link">{scrap.place.name}</Link> : null}
          {' · '}{statusName[scrap.status] ?? scrap.status}
          {scrap.source_url && <> · <a href={scrap.source_url} target="_blank" rel="noopener noreferrer" className="link">원문</a></>}
        </p>
        {!!promo.length && <p className="notice warn">홍보 글일 수 있어요 ({promo.join(', ')}). 라벨을 더 꼼꼼히 확인해 주세요.</p>}
        {!!scrap.content?.traveler_context.length && <div className="conditions">{scrap.content.traveler_context.map((c) => <span key={c}>{c}</span>)}</div>}

        {scrap.status === 'failed' && <p className="notice">모델 서버에 연결하지 못해 분석하지 못했어요. 글은 저장되어 있으니 다시 분석해 주세요.</p>}
        {scrap.status !== 'failed' && (scrap.annotations.length
          ? <section className="post-step">
              <h2>찾은 평가 {scrap.annotations.length}개</h2>
              <p className="muted">맞지 않는 평가는 체크를 해제하고 확정해 주세요. 확정한 평가만 내 비교 추천에 반영됩니다.</p>
              <ul className="scrap-rows">{scrap.annotations.map((a) => (
                <li key={a.annotation_id} className="scrap-row">
                  <input type="checkbox" aria-label={`${a.label} ${sentimentName[a.sentiment]} 선택`} checked={checked.has(a.annotation_id)} onChange={() => toggle(a.annotation_id)} />
                  <span><b>{a.label} · {sentimentName[a.sentiment] ?? a.sentiment}</b><small>“{a.evidence}”</small></span>
                  <span className="muted">{a.attribute}</span>
                </li>
              ))}</ul>
            </section>
          : <p className="notice">이 장소에 대한 평가를 찾지 못했어요. 장소 이름이 나오는 부분이 있는지 확인해 주세요.</p>)}

        {error && <p role="alert" className="auth-error">{error}</p>}
        {saved && <p className="muted">확정했어요. 내 스크랩의 비교 추천에 반영됩니다.</p>}
        <div className="compare-form">
          {!!scrap.annotations.length && <button type="button" disabled={busy !== ''} onClick={() => run('confirm', () => confirmScrapLabels(scrap.scrap_id, [...checked]))}>
            {busy === 'confirm' ? '저장 중…' : `확정 (${checked.size}개)`}
          </button>}
          <button type="button" className="secondary" disabled={busy !== ''} onClick={reanalyze}>
            {busy === 'analyze' ? '분석하는 중… (10초 정도 걸려요)' : '다시 분석'}
          </button>
        </div>

        <section className="post-step">
          <h2>본문</h2>
          <p className="post-content">{highlight(content, scrap.annotations.filter((a) => checked.has(a.annotation_id)))}</p>
        </section>
      </div>
    </>
  );
}
