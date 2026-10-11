import 'server-only';
import { cookies } from 'next/headers';
import { ApiError, isPlaceScrap } from './api';
import type { ExperimentMetricRow, Page, Place, PlaceDetail, PlaceProfile, Scrap, ScrapDetail, User } from './api-types';
import { TOKEN_COOKIE } from './session';

export function backendUrl(path: string): string {
  const backend = process.env.API_SERVER_URL?.replace(/\/$/, '');
  if (!backend) throw new ApiError('API_SERVER_URL이 설정되지 않았습니다.', 0);
  return `${backend}/api/v1${path}`;
}

export async function serverRequest<T>(path: string): Promise<T> {
  const url = backendUrl(path);
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  let response: Response;
  try {
    response = await fetch(url, { cache: 'no-store', headers: token ? { Authorization: `Bearer ${token}` } : undefined });
  } catch {
    throw new ApiError('API 서버에 연결할 수 없습니다.', 0);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(body?.error?.message ?? 'API 요청에 실패했습니다.', response.status, body?.error?.code);
  if (body === null) throw new ApiError('API 응답이 JSON이 아닙니다.', response.status);
  return body as T;
}

export const getPlaces = (page: number, size: number) => serverRequest<Page<Place>>(`/places?page=${page}&size=${size}`);
export const getPlaceDetail = (id: number) => serverRequest<PlaceDetail>(`/places/${id}`);

// These endpoints are reserved in the backend contract but are not implemented yet.
export const getPlaceProfile = (id: number) => serverRequest<PlaceProfile>(`/places/${id}/profile`);
export const getExperimentMetrics = () => serverRequest<ExperimentMetricRow[]>('/experiments');

export const getMyScraps = (page: number, size: number) => serverRequest<Page<Scrap>>(`/scraps?page=${page}&size=${size}`);
export const getScrapDetail = (scrapId: number) => serverRequest<ScrapDetail>(`/scraps/${scrapId}`);

/** 이 장소를 찜한 스크랩의 id. 찜하지 않았으면 null. */
export async function getPlaceScrapId(placeId: number): Promise<number | null> {
  const { items } = await serverRequest<Page<Scrap>>(`/scraps?place_id=${placeId}`);
  return items.find(isPlaceScrap)?.scrap_id ?? null;
}

/** 로그인한 사용자. 토큰이 없거나 만료됐으면 null. */
export async function getMe(): Promise<User | null> {
  if (!(await cookies()).has(TOKEN_COOKIE)) return null;
  try {
    return await serverRequest<User>('/users/me');
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
