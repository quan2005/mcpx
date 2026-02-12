import { useEffect, useState } from "react"
import type { ToolDetail } from "../api/client"
import { api } from "../api/client"
import { ToolTester } from "./ToolTester"

interface ToolDetailModalProps {
  isOpen: boolean
  server: string
  tool: string
  enabled: boolean
  onClose: () => void
  onToggle: () => void
  onRefresh: () => void
}

export function ToolDetailModal({
  isOpen,
  server,
  tool,
  enabled,
  onClose,
  onToggle,
  onRefresh,
}: ToolDetailModalProps) {
  const [detail, setDetail] = useState<ToolDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [showTester, setShowTester] = useState(false)
  const [isClosing, setIsClosing] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setIsClosing(false)
      setLoading(true)
      api
        .getTool(server, tool)
        .then(setDetail)
        .finally(() => setLoading(false))
    } else {
      setShowTester(false)
    }
  }, [isOpen, server, tool])

  const handleClose = () => {
    setIsClosing(true)
    setTimeout(onClose, 150)
  }

  const handleToggle = async () => {
    await onToggle()
    if (detail) {
      setDetail({ ...detail, enabled: !enabled })
    }
    onRefresh()
  }

  if (!isOpen) return null

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-150 ${
        isClosing ? "opacity-0" : "opacity-100"
      }`}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={handleClose} />

      {/* Modal */}
      <div
        className={`relative bg-slate-800 rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden border border-slate-700 transform transition-transform duration-150 ${
          isClosing ? "scale-95" : "scale-100"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold text-white">{tool}</h3>
            <span className="text-sm text-slate-400">({server})</span>
            {!enabled && (
              <span className="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-400">
                Disabled
              </span>
            )}
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-auto max-h-[calc(90vh-140px)]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-slate-400">Loading...</div>
            </div>
          ) : detail ? (
            <div className="space-y-4">
              {/* Description */}
              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-1">Description</h4>
                <p className="text-slate-200">{detail.description || "No description"}</p>
              </div>

              {/* Input Schema */}
              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-1">Input Schema</h4>
                <pre className="bg-slate-900 p-3 rounded-lg text-sm text-slate-300 overflow-auto max-h-64">
                  {JSON.stringify(detail.input_schema, null, 2)}
                </pre>
              </div>

              {/* Tester */}
              {showTester && (
                <div className="border-t border-slate-700 pt-4">
                  <h4 className="text-sm font-medium text-slate-400 mb-2">Test Tool</h4>
                  <ToolTester
                    server={server}
                    tool={tool}
                    schema={detail.input_schema}
                    enabled={enabled}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-400">Failed to load tool details</div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-700 bg-slate-900/50">
          <div className="flex gap-2">
            <button
              onClick={() => setShowTester(!showTester)}
              disabled={!enabled}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                enabled
                  ? "bg-blue-600 hover:bg-blue-700 text-white"
                  : "bg-slate-700 text-slate-500 cursor-not-allowed"
              }`}
            >
              {showTester ? "Hide Tester" : "Test Tool"}
            </button>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-sm text-slate-400">{enabled ? "Enabled" : "Disabled"}</span>
              <input
                type="checkbox"
                className="toggle"
                checked={enabled}
                onChange={handleToggle}
              />
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}
