import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Check, CircleAlert, Info, LoaderCircle, X } from 'lucide-react'

export type StatusTone = 'info' | 'success' | 'warning' | 'danger'

export function Button({ variant = 'default', icon, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'subtle' | 'danger'; icon?: ReactNode }) {
  return <button className={`btn btn-${variant}`} {...props}>{icon}{children}</button>
}

export function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button className="btn btn-icon" aria-label={label} title={label} {...props}>{children}</button>
}

export function Status({ tone, title, children }: { tone: StatusTone; title?: string; children: ReactNode }) {
  const Icon = tone === 'success' ? Check : tone === 'danger' ? X : tone === 'warning' ? CircleAlert : Info
  return <div className={`status status-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}><Icon size={17} aria-hidden="true" /><div>{title && <strong>{title} </strong>}{children}</div></div>
}

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return <div className="empty" role="status"><LoaderCircle size={24} className="spin" aria-hidden="true" /><span>{label}</span></div>
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return <div className="empty"><CircleAlert size={28} color="var(--color-danger)" aria-hidden="true" /><strong>{title}</strong><span>{message}</span>{onRetry && <Button variant="subtle" onClick={onRetry}>Try again</Button>}</div>
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return <div className="empty"><strong>{title}</strong><span>{message}</span>{action}</div>
}

export function Badge({ difficulty }: { difficulty: 'easy' | 'mid' | 'hard' }) {
  return <span className={`badge badge-${difficulty}`}>{difficulty === 'mid' ? 'mid' : difficulty}</span>
}

export function SectionHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="panel-head"><div><h3>{title}</h3>{description && <p>{description}</p>}</div>{action}</div>
}
