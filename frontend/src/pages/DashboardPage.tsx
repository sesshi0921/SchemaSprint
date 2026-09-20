import { Check, CalendarDays } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { useLocale } from '../lib/i18n'
import type { Dashboard, SessionState } from '../lib/types'
import { ErrorState, LoadingState, SectionHeader } from '../design-system'

const JST = 'Asia/Tokyo'
function jstParts(date = new Date()) { const parts = new Intl.DateTimeFormat('en-US', { timeZone: JST, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date); return Object.fromEntries(parts.filter((item) => item.type !== 'literal').map((item) => [item.type, Number(item.value)])) as { year: number; month: number; day: number } }
function iso(year: number, month: number, day: number) { return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}` }

export function DashboardPage({ session }: { session?: SessionState | null }) {
  const { locale } = useLocale(session?.profile?.locale)
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')
  const now = jstParts()
  const from = iso(now.year, now.month, 1)
  const to = iso(now.year, now.month, new Date(Date.UTC(now.year, now.month, 0)).getUTCDate())
  useEffect(() => { api.dashboard(from, to).then(setData).catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load dashboard.')) }, [from, to])
  const cells = useMemo(() => {
    const first = new Date(Date.UTC(now.year, now.month - 1, 1))
    const offset = (first.getUTCDay() + 6) % 7
    const days = new Date(Date.UTC(now.year, now.month, 0)).getUTCDate()
    const map = new Map((data?.calendar ?? []).map((item) => [item.publicationDate, item.passedProblemIds.length > 0]))
    return [...Array(offset).fill(null), ...Array.from({ length: days }, (_, index) => index + 1)].map((day) => {
      if (day === null) return null
      const date = iso(now.year, now.month, day)
      return { day, date, passed: map.get(date) ?? false, today: date === iso(now.year, now.month, now.day) }
    })
  }, [data, now.day, now.month, now.year])
  if (error) return <main className="page"><ErrorState message={error} onRetry={() => window.location.reload()} /></main>
  if (!data) return <LoadingState label="Loading your practice…" />
  const monthLabel = new Intl.DateTimeFormat(locale, { timeZone: JST, month: 'long', year: 'numeric' }).format(new Date(Date.UTC(now.year, now.month - 1, 1)))
  return <main className="page dashboard-page"><div className="page-header"><div><h2>Your dashboard</h2><p>JST practice days, passed problems, and a compact history of your work.</p></div></div><div className="summary-line" aria-label="Practice summary"><div><span>Unique problems passed</span><strong>{data.uniquePassed}</strong></div><div><span>Easy · Mid · Hard</span><strong>{data.byDifficulty.easy ?? 0} · {data.byDifficulty.mid ?? 0} · {data.byDifficulty.hard ?? 0}</strong></div><div><span>Most practiced weekday</span><strong>{weekdayName(data.byWeekday)}</strong></div></div><section className="dashboard-grid"><div className="panel"><SectionHeader title={monthLabel} description="A checkmark means at least one problem was passed on that JST day." /><div className="panel-pad"><div className="calendar">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => <div key={day} className="calendar-head">{day}</div>)}{cells.map((cell, index) => cell ? <div key={cell.date} className={`calendar-cell ${cell.passed ? 'is-passed' : ''} ${cell.today ? 'is-today' : ''}`} aria-label={`${cell.date}${cell.passed ? ': passed' : ': not passed'}`}>{cell.passed && <Check size={13} aria-hidden="true" />}<span>{cell.day}</span></div> : <div key={`empty-${index}`} className="calendar-cell is-empty" aria-hidden="true" />)}</div></div></div><div className="panel"><SectionHeader title="By weekday" description="Unique passes only; this is not a leaderboard." /><div className="panel-pad stack weekday-list">{Object.entries(data.byWeekday).map(([day, count]) => <div key={day} className="weekday-row"><span>{day}</span><div className="weekday-bar" aria-hidden="true"><div style={{ width: `${Math.min(100, count * 12)}%` }} /></div><strong>{count}</strong></div>)}</div></div></section><p className="dashboard-note"><CalendarDays size={15} aria-hidden="true" />The dashboard does not calculate a score or rank; it only records completed practice.</p></main>
}
function weekdayName(values: Record<string, number>) { const [day] = Object.entries(values).sort((a, b) => b[1] - a[1])[0] ?? ['—']; return day || '—' }
