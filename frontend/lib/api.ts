import type {
  AnalysisResult, AnalyzeRequest, EvidenceReview, ExperimentMetricRow, FitResult, Place, Page, RecommendationQuery, Scrap,
  ScrapRecommendation,
} from './api-types';

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, { cache: 'no-store', ...init });
  } catch {
    throw new ApiError('API 서버에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인해 주세요.', 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    const fallback = response.status === 401 ? '로그인이 필요합니다.' : 'API 요청에 실패했습니다. 서버 실행 상태를 확인해 주세요.';
    throw new ApiError(
      typeof error?.message === 'string' ? error.message : fallback,
      response.status,
      error?.code,
    );
  }
  if (response.status === 204) return undefined as T;
  if (body === null) throw new ApiError('API 응답이 JSON이 아닙니다.', response.status);
  return body as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export function getRecommendations(query: RecommendationQuery): Promise<FitResult[]> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return apiRequest<FitResult[]>(`/recommendations?${params}`);
}

export function getEvidence(placeId: number, aspect: string, sentiment?: string): Promise<EvidenceReview[]> {
  const params = new URLSearchParams({ aspect });
  if (sentiment) params.set('sentiment', sentiment);
  return apiRequest<EvidenceReview[]>(`/places/${placeId}/evidence?${params}`);
}

export function analyzeReview(request: AnalyzeRequest): Promise<AnalysisResult> {
  return apiRequest<AnalysisResult>('/analyze', json('POST', request));
}

export function getExperiments(): Promise<ExperimentMetricRow[]> {
  return apiRequest<ExperimentMetricRow[]>('/experiments');
}

export function getPlaces(query: Record<string, string>): Promise<Page<Place>> {
  return apiRequest<Page<Place>>(`/places?${new URLSearchParams(query)}`);
}

export const createPlaceScrap = (placeId: number, title: string | null) =>
  apiRequest<Scrap>('/scraps', json('POST', { place_id: placeId, title }));
export const deleteScrap = (scrapId: number) => apiRequest<void>(`/scraps/${scrapId}`, { method: 'DELETE' });
export const getScrapsForPlace = (placeId: number) => apiRequest<Page<Scrap>>(`/scraps?place_id=${placeId}`);

/** 스크랩한 장소끼리 요구사항으로 비교한다. 요구사항 해석에 파인튜닝 모델을 한 번 쓴다. */
export const compareScraps = (scrapIds: number[], requirements: string) =>
  apiRequest<ScrapRecommendation>('/recommendations', json('POST', { scrap_ids: scrapIds, requirements }));

/** 장소 자체를 찜한 스크랩(리뷰·외부 글 스크랩 제외). */
export const isPlaceScrap = (scrap: Scrap) => scrap.review_id === null && scrap.source_url === null;
