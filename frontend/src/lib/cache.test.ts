import { describe, expect, it } from 'vitest'
import { isRetryableQueueError, nextBackoffMs } from './cache'

describe('durable queue policy', () => {
  it('classifies network and retryable HTTP failures without treating conflicts as retryable', () => {
    expect(isRetryableQueueError(new TypeError('offline'))).toBe(true)
    expect(isRetryableQueueError({ status: 503 })).toBe(true)
    expect(isRetryableQueueError({ status: 409 })).toBe(false)
  })
  it('bounds exponential backoff', () => {
    expect(nextBackoffMs(0, 0)).toBeGreaterThanOrEqual(1000)
    expect(nextBackoffMs(99, 0)).toBeLessThanOrEqual(300000)
    expect(nextBackoffMs(1, 10)).toBeGreaterThanOrEqual(10000)
  })
})
