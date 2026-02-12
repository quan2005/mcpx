import { useCallback, useEffect, useState } from "react"

interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  variant?: "danger" | "warning" | "info"
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  variant = "warning",
  confirmText = "Confirm",
  cancelText = "Cancel",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [isClosing, setIsClosing] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setIsClosing(false)
    }
  }, [isOpen])

  const handleClose = () => {
    setIsClosing(true)
    setTimeout(onCancel, 150) // Wait for animation
  }

  if (!isOpen) return null

  const variantStyles = {
    danger: {
      icon: "⚠️",
      iconBg: "bg-red-900",
      button: "bg-red-600 hover:bg-red-700",
    },
    warning: {
      icon: "⚠️",
      iconBg: "bg-yellow-900",
      button: "bg-yellow-600 hover:bg-yellow-700",
    },
    info: {
      icon: "ℹ️",
      iconBg: "bg-blue-900",
      button: "bg-blue-600 hover:bg-blue-700",
    },
  }

  const styles = variantStyles[variant]

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-150 ${
        isClosing ? "opacity-0" : "opacity-100"
      }`}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={handleClose} />

      {/* Dialog */}
      <div
        className={`relative bg-slate-800 rounded-xl shadow-2xl max-w-md w-full mx-4 border border-slate-700 transform transition-transform duration-150 ${
          isClosing ? "scale-95" : "scale-100"
        }`}
      >
        <div className="p-6">
          <div className="flex items-start gap-4">
            <div
              className={`flex-shrink-0 w-10 h-10 rounded-full ${styles.iconBg} flex items-center justify-center text-xl`}
            >
              {styles.icon}
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-white">{title}</h3>
              <p className="mt-2 text-slate-300">{message}</p>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
            >
              {cancelText}
            </button>
            <button
              onClick={() => {
                setIsClosing(true)
                setTimeout(onConfirm, 150)
              }}
              className={`px-4 py-2 rounded-lg text-white transition-colors ${styles.button}`}
            >
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Hook for async confirm dialog
export function useConfirmDialog() {
  const [state, setState] = useState<{
    isOpen: boolean
    resolve: ((value: boolean) => void) | null
    props: Omit<ConfirmDialogProps, "isOpen" | "onConfirm" | "onCancel">
  }>({
    isOpen: false,
    resolve: null,
    props: { title: "", message: "" },
  })

  const confirm = useCallback(
    (props: Omit<ConfirmDialogProps, "isOpen" | "onConfirm" | "onCancel">): Promise<boolean> => {
      return new Promise((resolve) => {
        setState({ isOpen: true, resolve, props })
      })
    },
    []
  )

  const handleConfirm = useCallback(() => {
    state.resolve?.(true)
    setState((prev) => ({ ...prev, isOpen: false }))
  }, [state.resolve])

  const handleCancel = useCallback(() => {
    state.resolve?.(false)
    setState((prev) => ({ ...prev, isOpen: false }))
  }, [state.resolve])

  const dialog = (
    <ConfirmDialog
      isOpen={state.isOpen}
      {...state.props}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    />
  )

  return { confirm, dialog }
}
