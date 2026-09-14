import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Inbox,
  LoaderCircle,
  RefreshCw,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { titleCase } from '../lib/format'

export function Button({ className = '', variant = 'primary', size = 'medium', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'small' | 'medium' }) {
  return (
    <button className={`button button--${variant} button--${size} ${className}`.trim()} {...props}>
      {children}
    </button>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`.trim()}>{children}</section>
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  )
}

export function Badge({ children, tone = 'neutral', dot = false }: { children: ReactNode; tone?: string; dot?: boolean }) {
  return (
    <span className={`badge badge--${tone.toLowerCase().replaceAll(' ', '-')}`}>
      {dot && <span className="badge__dot" aria-hidden="true" />}
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status?: string }) {
  const normalized = (status || 'unknown').toLowerCase()
  return (
    <Badge tone={normalized} dot>
      {titleCase(normalized)}
    </Badge>
  )
}

export function ProgressBar({ value, tone = 'teal', label }: { value: number; tone?: 'teal' | 'blue' | 'amber' | 'red'; label?: string }) {
  const safeValue = Math.min(100, Math.max(0, value))
  return (
    <div className="progress" aria-label={label} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(safeValue)}>
      <span className={`progress__bar progress__bar--${tone}`} style={{ width: `${safeValue}%` }} />
    </div>
  )
}

export function Modal({ title, description, children, onClose, size = 'medium' }: { title: string; description?: string; children: ReactNode; onClose: () => void; size?: 'small' | 'medium' | 'large' }) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKeyDown)
    document.body.classList.add('modal-open')
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.classList.remove('modal-open')
    }
  }, [onClose])

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className={`modal modal--${size}`} role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal__header">
          <div>
            <h2 id="modal-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={19} /></button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, hint, error, required, children }: { label: string; hint?: string; error?: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field__label">{label}{required && <span aria-hidden="true"> *</span>}</span>
      {children}
      {error ? <span className="field__error">{error}</span> : hint ? <span className="field__hint">{hint}</span> : null}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${props.className || ''}`.trim()} {...props} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`select ${props.className || ''}`.trim()} {...props} />
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`textarea ${props.className || ''}`.trim()} {...props} />
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }: { icon?: LucideIcon; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon"><Icon size={24} /></span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}

export function LoadingState({ label = 'Loading data…' }: { label?: string }) {
  return <div className="loading-state"><LoaderCircle className="spin" size={20} /><span>{label}</span></div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state">
      <AlertTriangle size={20} />
      <span>{message}</span>
      {onRetry && <Button size="small" variant="secondary" onClick={onRetry}><RefreshCw size={14} /> Retry</Button>}
    </div>
  )
}

export function TableContainer({ children }: { children: ReactNode }) {
  return <div className="table-container"><table className="data-table">{children}</table></div>
}

export function Pagination({ page, pages, total, pageSize, onPageChange, hasNext, totalExact = true }: { page: number; pages: number; total: number; pageSize: number; onPageChange: (page: number) => void; hasNext?: boolean; totalExact?: boolean }) {
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(total, page * pageSize)
  return (
    <div className="pagination">
      <span>{first}–{last}{totalExact ? ` of ${total}` : hasNext ? '+' : ''}</span>
      <div>
        <button type="button" className="icon-button" aria-label="Previous page" disabled={page <= 1} onClick={() => onPageChange(page - 1)}><ChevronLeft size={18} /></button>
        <span className="pagination__page">Page {page}{totalExact ? ` of ${Math.max(1, pages)}` : ''}</span>
        <button type="button" className="icon-button" aria-label="Next page" disabled={hasNext === undefined ? page >= pages : !hasNext} onClick={() => onPageChange(page + 1)}><ChevronRight size={18} /></button>
      </div>
    </div>
  )
}

export function SkeletonRows({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <tbody aria-label="Loading">
      {Array.from({ length: rows }, (_, row) => (
        <tr key={row}>{Array.from({ length: columns }, (_, column) => <td key={column}><span className="skeleton-line" /></td>)}</tr>
      ))}
    </tbody>
  )
}
