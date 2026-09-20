import type { CanonicalSchema, Dashboard, Draft, EditorSources, Feedback, Job, Locale, NoticePage, PostPage, ProblemDetail, ProblemError, ProblemSummary, Profile, SessionState, Submission } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'
export class ApiError extends Error { constructor(public readonly status: number, public readonly problem: ProblemError) { super(problem.detail || problem.title); } }
function idempotencyKey() { return crypto.randomUUID() }
function parseProblem(value: unknown, fallback: ProblemError): ProblemError {
  if (!value || typeof value !== 'object') return fallback
  const item = value as Partial<ProblemError>
  return typeof item.code === 'string' && typeof item.title === 'string' ? { ...fallback, ...item, status: typeof item.status === 'number' ? item.status : fallback.status } : fallback
}
async function request<T>(path: string, init: RequestInit = {}, csrfToken?: string, operationId?: string): Promise<T> {
  const headers = new Headers(init.headers); if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json'); if (csrfToken) headers.set('X-CSRF-Token', csrfToken); if (['POST','PUT','PATCH','DELETE'].includes(init.method?.toUpperCase() ?? '')) headers.set('Idempotency-Key', operationId ?? idempotencyKey());
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' });
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') ?? ''; const bodyText = await response.text(); let body: unknown; try { body = bodyText ? JSON.parse(bodyText) : {} } catch { throw new ApiError(502, { type: 'about:blank', title: 'API unavailable', status: 502, code: 'api_invalid_response', detail: 'The API returned an unreadable response.', retryable: true }) }
  if (!response.ok) throw new ApiError(response.status, parseProblem(body, { type: 'about:blank', title: response.statusText || 'Request failed', status: response.status, code: 'request_failed', retryable: response.status >= 500 })); if (bodyText && !contentType.includes('json')) throw new ApiError(502, { type: 'about:blank', title: 'API unavailable', status: 502, code: 'api_invalid_response', detail: 'The API returned an unexpected response.', retryable: true }); return body as T;
}
export const api = {
  session: () => request<SessionState>('/v1/session'),
  logout: (csrf: string) => request<void>('/v1/session/logout', { method: 'POST' }, csrf),
  onboarding: (body: { isAtLeast16: true; displayName?: string; policyVersionIds: string[] }, csrf: string) => request<Profile>('/v1/onboarding', { method: 'POST', body: JSON.stringify(body) }, csrf),
  policies: () => request<unknown[]>('/v1/policies'),
  profile: () => request<Profile>('/v1/profile'),
  updateProfile: (patch: Partial<Pick<Profile, 'displayName' | 'locale' | 'theme'>>, csrf: string) => request<Profile>('/v1/profile', { method: 'PATCH', body: JSON.stringify(patch), headers: { 'Content-Type': 'application/merge-patch+json' } }, csrf),
  today: (locale: Locale = 'en') => request<ProblemDetail>(`/v1/problems/today?locale=${encodeURIComponent(locale)}`),
  problems: (params: URLSearchParams = new URLSearchParams(), locale: Locale = 'en') => { const query = new URLSearchParams(params); query.set('locale', locale); return request<{ items: ProblemSummary[]; nextCursor?: string | null }>(`/v1/problems?${query.toString()}`) },
  problem: (id: string, locale: Locale = 'en') => request<ProblemDetail>(`/v1/problems/${encodeURIComponent(id)}?locale=${encodeURIComponent(locale)}`),
  draft: (id: string) => request<Draft>(`/v1/problems/${encodeURIComponent(id)}/draft`),
  saveDraft: (id: string, body: { canonicalSchema: CanonicalSchema; editorSources: EditorSources; layout: Record<string, unknown> }, revision: number, csrf: string) => request<Draft>(`/v1/problems/${encodeURIComponent(id)}/draft`, { method: 'PUT', headers: { 'If-Match': `"${revision}"` }, body: JSON.stringify(body) }, csrf),
  submit: (body: { problemId: string; problemVersionId: string; canonicalSchema: CanonicalSchema; editorSources: EditorSources; staticAnalysis: { parserVersion: string; diagnostics: Record<string, unknown>[] } }, csrf: string, operationId?: string) => request<Submission>('/v1/submissions', { method: 'POST', body: JSON.stringify(body) }, csrf, operationId),
  submission: (id: string) => request<Submission>(`/v1/submissions/${encodeURIComponent(id)}`),
  feedback: (id: string, locale: Locale = 'en') => request<Feedback[]>(`/v1/submissions/${encodeURIComponent(id)}/feedback?locale=${encodeURIComponent(locale)}`),
  requestFeedback: (id: string, csrf: string, rewardAttemptId?: string) => request<Job>(`/v1/submissions/${encodeURIComponent(id)}/feedback`, { method: 'POST', body: JSON.stringify(rewardAttemptId ? { rewardAttemptId } : {}) }, csrf),
  feedbackReward: (csrf: string) => request<unknown>('/v1/feedback-rewards', { method: 'POST' }, csrf),
  translation: (kind: string, id: string, version: number, locale: Locale = 'en') => request<unknown>(`/v1/translations/${encodeURIComponent(kind)}/${encodeURIComponent(id)}?contentVersion=${version}&locale=${encodeURIComponent(locale)}`),
  dashboard: (from?: string, to?: string) => { const query = new URLSearchParams(); if (from) { query.set('from', from); query.set('to', to ?? from) } return request<Dashboard>(`/v1/dashboard${query.toString() ? `?${query.toString()}` : ''}`) },
  posts: (id: string, locale: Locale = 'en', cursor?: string) => { const query = new URLSearchParams({ locale }); if (cursor) query.set('cursor', cursor); return request<PostPage>(`/v1/problems/${encodeURIComponent(id)}/posts?${query.toString()}`) },
  createPost: (problemId: string, body: { submissionId: string; explanation: string }, csrf: string) => request<unknown>(`/v1/problems/${encodeURIComponent(problemId)}/posts`, { method: 'POST', body: JSON.stringify(body) }, csrf),
  report: (body: Record<string, unknown>, csrf: string) => request<unknown>('/v1/reports', { method: 'POST', body: JSON.stringify(body) }, csrf),
  notices: (locale: Locale = 'en', cursor?: string) => { const query = new URLSearchParams({ locale }); if (cursor) query.set('cursor', cursor); return request<NoticePage>(`/v1/notices?${query.toString()}`) },
  markNoticeRead: (id: string, csrf: string) => request<void>(`/v1/notices/${encodeURIComponent(id)}/read`, { method: 'PUT' }, csrf),
  job: (id: string) => request<Job>(`/v1/jobs/${encodeURIComponent(id)}`),
  exportAccount: (csrf: string) => request<Job>('/v1/account/export', { method: 'POST' }, csrf),
  deleteAccount: (proof: string, csrf: string) => request<void | Job>('/v1/account', { method: 'DELETE', headers: { 'X-Reauthentication-Proof': proof } }, csrf),
}
