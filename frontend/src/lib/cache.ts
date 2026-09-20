import type { Draft, ProblemDetail, ProblemSummary } from './types'

/** Account-owned browser state. The server remains the source of truth. */
const DB_NAME = 'schemasprint-v1'
const VERSION = 2
const stores = ['problems', 'details', 'drafts', 'queue', 'meta'] as const
type StoreName = typeof stores[number]
export type QueueState = 'queued' | 'sending' | 'attention'
export type QueueRecord<T = unknown> = { operationId: string; body: T; queuedAt: string; state: QueueState; attempts: number; nextAttemptAt: number; leaseUntil?: number; lastError?: string }
export type ClaimedQueue<T> = { key: IDBValidKey; value: QueueRecord<T> }
let dbPromise: Promise<IDBDatabase> | null = null

function openDb() {
  if (typeof indexedDB === 'undefined') return Promise.reject(new Error('IndexedDB unavailable'))
  dbPromise ??= new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, VERSION)
    request.onupgradeneeded = (event) => { const db = request.result; stores.forEach((store) => { if (!db.objectStoreNames.contains(store)) db.createObjectStore(store) }); const oldVersion = (event as IDBVersionChangeEvent).oldVersion; if (oldVersion < 2 && db.objectStoreNames.contains('queue')) { const queue = (event.target as IDBOpenDBRequest).transaction?.objectStore('queue'); const cursorRequest = queue?.openCursor(); if (cursorRequest) cursorRequest.onsuccess = (cursorEvent) => { const cursor = (cursorEvent.target as IDBRequest<IDBCursorWithValue>).result; if (!cursor) return; const value = cursor.value as Partial<QueueRecord>; if (!value.state || !value.nextAttemptAt) cursor.update({ ...value, state: 'queued', attempts: value.attempts ?? 0, nextAttemptAt: Date.now() }); cursor.continue() } } }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('Cache unavailable'))
  })
  return dbPromise
}
function key(accountId: string, id: string) { return `${accountId}:${id}` }
async function transaction<T>(storeNames: StoreName[], mode: IDBTransactionMode, fn: (tx: IDBTransaction) => Promise<T> | T): Promise<T> {
  const db = await openDb(); const tx = db.transaction(storeNames, mode); const result = await fn(tx)
  await new Promise<void>((resolve, reject) => { tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error ?? new Error('Cache transaction failed')); tx.onabort = () => reject(tx.error ?? new Error('Cache transaction aborted')) })
  return result
}
async function put<T>(store: StoreName, id: string, value: T) { return transaction([store], 'readwrite', (tx) => { tx.objectStore(store).put(value, id) }) }
async function get<T>(store: StoreName, id: IDBValidKey) { const db = await openDb(); return new Promise<T | undefined>((resolve, reject) => { const request = db.transaction(store, 'readonly').objectStore(store).get(id); request.onsuccess = () => resolve(request.result as T | undefined); request.onerror = () => reject(request.error ?? new Error('Cache read failed')) }) }
async function listByPrefix<T>(store: StoreName, prefix: string) { const db = await openDb(); return new Promise<{ key: IDBValidKey; value: T }[]>((resolve, reject) => { const values: { key: IDBValidKey; value: T }[] = []; const request = db.transaction(store, 'readonly').objectStore(store).openCursor(); request.onsuccess = () => { const cursor = request.result; if (!cursor) return resolve(values); if (String(cursor.key).startsWith(prefix)) values.push({ key: cursor.key, value: cursor.value as T }); cursor.continue() }; request.onerror = () => reject(request.error ?? new Error('Cache list failed')) }) }
async function remove(store: StoreName, id: IDBValidKey) { return transaction([store], 'readwrite', (tx) => { tx.objectStore(store).delete(id) }) }
const retryableStatus = (status: number) => status === 408 || status === 425 || status === 429 || status >= 500
export const isRetryableQueueError = (error: unknown) => { if (error instanceof TypeError) return true; const status = (error as { status?: unknown })?.status; return typeof status === 'number' && retryableStatus(status) }
export const nextBackoffMs = (attempts: number, retryAfterSeconds?: number) => Math.min(5 * 60_000, Math.max(1_000, (retryAfterSeconds ?? 0) * 1_000, 1_000 * 2 ** Math.min(attempts, 8)) + Math.floor(Math.random() * 500))

export const cache = {
  putProblems: (accountId: string, items: ProblemSummary[]) => Promise.all(items.map((item) => put('problems', key(accountId, item.id), item))),
  problem: (accountId: string, id: string) => get<ProblemSummary>('problems', key(accountId, id)),
  putDetail: (accountId: string, item: ProblemDetail) => Promise.all([put('details', key(accountId, item.id), item), put('details', key(accountId, 'today'), item)]).then(() => undefined),
  detail: (accountId: string, id: string) => get<ProblemDetail>('details', key(accountId, id)),
  putDraft: (accountId: string, draft: Draft) => put('drafts', key(accountId, draft.problemId), draft),
  draft: (accountId: string, problemId: string) => get<Draft>('drafts', key(accountId, problemId)),
  putConflict: (accountId: string, draft: Draft) => put('drafts', key(accountId, `conflict:${draft.problemId}`), draft),
  conflict: (accountId: string, problemId: string) => get<Draft>('drafts', key(accountId, `conflict:${problemId}`)),
  queue: async <T>(accountId: string, payload: { operationId: string; body: T }) => put<QueueRecord<T>>('queue', key(accountId, payload.operationId), { ...payload, queuedAt: new Date().toISOString(), state: 'queued', attempts: 0, nextAttemptAt: Date.now() }),
  queued: <T>(accountId: string) => listByPrefix<QueueRecord<T>>('queue', `${accountId}:`),
  claimQueued: async <T>(accountId: string, limit = 8): Promise<ClaimedQueue<T>[]> => transaction(['queue'], 'readwrite', async (tx) => {
    const result: ClaimedQueue<T>[] = []
    await new Promise<void>((resolve, reject) => { const request = tx.objectStore('queue').openCursor(); request.onsuccess = () => { const cursor = request.result; if (!cursor || result.length >= limit) return resolve(); if (String(cursor.key).startsWith(`${accountId}:`)) { const value = cursor.value as QueueRecord<T>; const available = value.state === 'queued' || (value.state === 'sending' && (value.leaseUntil ?? 0) < Date.now()); if (available && value.nextAttemptAt <= Date.now()) { const claimed = { ...value, state: 'sending' as const, leaseUntil: Date.now() + 30_000 }; cursor.update(claimed); result.push({ key: cursor.key, value: claimed }) } } cursor.continue() }; request.onerror = () => reject(request.error ?? new Error('Queue claim failed')) })
    return result
  }),
  ackQueued: (keyValue: IDBValidKey) => remove('queue', keyValue),
  failQueued: async (keyValue: IDBValidKey, error: string, retry: boolean, retryAfterSeconds?: number) => { const current = await get<QueueRecord>('queue', keyValue); if (!current) return; if (!retry || current.attempts >= 8) return put('queue', String(keyValue), { ...current, state: 'attention', leaseUntil: undefined, lastError: error }); return put('queue', String(keyValue), { ...current, state: 'queued', attempts: current.attempts + 1, nextAttemptAt: Date.now() + nextBackoffMs(current.attempts, retryAfterSeconds), leaseUntil: undefined, lastError: error }) },
  clearAccount: async (accountId: string) => { const db = await openDb(); try { await new Promise<void>((resolve, reject) => { const tx = db.transaction(stores, 'readwrite'); stores.forEach((store) => { const request = tx.objectStore(store).openCursor(); request.onsuccess = () => { const cursor = request.result; if (!cursor) return; if (String(cursor.key).startsWith(`${accountId}:`)) cursor.delete(); cursor.continue() } }); tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error ?? new Error('Cache purge failed')) }) } finally { db.close(); dbPromise = null } },
  withAccountLease: async <T>(accountId: string, work: () => Promise<T>) => { if ('locks' in navigator && navigator.locks?.request) return navigator.locks.request(`schemasprint-queue:${accountId}`, { mode: 'exclusive' }, work); const leaseKey = key(accountId, 'queue-lease'); const existing = await get<{ until: number }>('meta', leaseKey); if (existing && existing.until > Date.now()) return undefined; await put('meta', leaseKey, { until: Date.now() + 30_000 }); try { return await work() } finally { await remove('meta', leaseKey).catch(() => undefined) } },
}
