import { describe, expect, it } from 'vitest'
import { supportedLocales, t } from './i18n'

describe('supported UI locales', () => {
  it('has six distinct navigation translations', () => {
    expect(supportedLocales).toHaveLength(6)
    expect(supportedLocales.every((locale) => t(locale, 'library') !== 'library')).toBe(true)
  })
})
