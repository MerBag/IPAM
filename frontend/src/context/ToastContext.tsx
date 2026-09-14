import { CheckCircle2, CircleAlert, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'

type ToastTone = 'success' | 'error' | 'info'
type ToastItem = { id: number; message: string; tone: ToastTone }
type ToastContextValue = { notify: (message: string, tone?: ToastTone) => void }

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), [])
  const notify = useCallback(
    (message: string, tone: ToastTone = 'success') => {
      const id = nextId.current++
      setToasts((current) => [...current.slice(-2), { id, message, tone }])
      window.setTimeout(() => dismiss(id), 4500)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ notify }), [notify])
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => {
          const Icon = toast.tone === 'success' ? CheckCircle2 : toast.tone === 'error' ? CircleAlert : Info
          return (
            <div className={`toast toast--${toast.tone}`} key={toast.id}>
              <Icon size={18} aria-hidden="true" />
              <span>{toast.message}</span>
              <button type="button" className="icon-button icon-button--small" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification">
                <X size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const value = useContext(ToastContext)
  if (!value) throw new Error('useToast must be used inside ToastProvider')
  return value
}
