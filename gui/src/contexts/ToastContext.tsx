import { createContext, useCallback, useContext, useState } from "react"

export interface Toast {
  id: string
  type: "success" | "error" | "warning" | "info"
  message: string
  duration?: number
}

interface ToastContextValue {
  toasts: Toast[]
  showToast: (toast: Omit<Toast, "id">) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const showToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = crypto.randomUUID()
    const newToast = { ...toast, id }
    setToasts((prev) => [...prev, newToast])

    // Auto remove after duration
    const duration = toast.duration ?? 3000
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, duration)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast }}>
      {children}
      <ToastContainer />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error("useToast must be used within ToastProvider")
  }
  return context
}

function ToastContainer() {
  const { toasts, removeToast } = useToast()

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const bgColors = {
    success: "bg-green-900 border-green-700",
    error: "bg-red-900 border-red-700",
    warning: "bg-yellow-900 border-yellow-700",
    info: "bg-blue-900 border-blue-700",
  }

  const textColors = {
    success: "text-green-300",
    error: "text-red-300",
    warning: "text-yellow-300",
    info: "text-blue-300",
  }

  const icons = {
    success: "✓",
    error: "✕",
    warning: "⚠",
    info: "ℹ",
  }

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg min-w-80 animate-slide-in ${bgColors[toast.type]}`}
    >
      <span className={`text-lg ${textColors[toast.type]}`}>{icons[toast.type]}</span>
      <p className={`flex-1 ${textColors[toast.type]}`}>{toast.message}</p>
      <button
        onClick={onClose}
        className={`p-1 hover:opacity-70 ${textColors[toast.type]}`}
        aria-label="Close"
      >
        ✕
      </button>
    </div>
  )
}
