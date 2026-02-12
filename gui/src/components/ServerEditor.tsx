import { useEffect, useState } from "react"

export interface ServerConfig {
  type: "stdio" | "http"
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  enabled: boolean
}

interface ServerEditorProps {
  isOpen: boolean
  serverName?: string // undefined = new server
  initialConfig?: ServerConfig
  onSave: (name: string, config: ServerConfig) => void
  onDelete?: () => void
  onClose: () => void
}

type InputMode = "form" | "json"

export function ServerEditor({
  isOpen,
  serverName,
  initialConfig,
  onSave,
  onDelete,
  onClose,
}: ServerEditorProps) {
  const [name, setName] = useState("")
  const [config, setConfig] = useState<ServerConfig>({
    type: "stdio",
    command: "",
    args: [],
    env: {},
    enabled: true,
  })
  const [argsText, setArgsText] = useState("")
  const [envRows, setEnvRows] = useState<[string, string][]>([])
  const [headerRows, setHeaderRows] = useState<[string, string][]>([])
  const [isClosing, setIsClosing] = useState(false)
  const [inputMode, setInputMode] = useState<InputMode>("form")
  const [jsonText, setJsonText] = useState("")
  const [jsonError, setJsonError] = useState<string | null>(null)

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setIsClosing(false)
      setName(serverName || "")
      setConfig(
        initialConfig || {
          type: "stdio",
          command: "",
          args: [],
          env: {},
          enabled: true,
        }
      )
      setArgsText(initialConfig?.args?.join(" ") || "")
      setEnvRows(Object.entries(initialConfig?.env || {}))
      setHeaderRows(Object.entries(initialConfig?.headers || {}))
      setInputMode("form")
      setJsonText("")
      setJsonError(null)
    }
  }, [isOpen, serverName, initialConfig])

  const handleClose = () => {
    setIsClosing(true)
    setTimeout(onClose, 150)
  }

  const handleSave = () => {
    const finalConfig: ServerConfig = {
      ...config,
      args: argsText.split(" ").filter(Boolean),
      env: envRows.reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {}),
    }

    if (config.type === "http") {
      finalConfig.headers = headerRows.reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {})
    }

    onSave(name, finalConfig)
    handleClose()
  }

  const handleJsonSave = () => {
    if (!jsonText.trim()) {
      setJsonError("Please enter JSON configuration")
      return
    }

    try {
      const parsed = JSON.parse(jsonText)

      // Only support mcpServers format: { "server-name": { ...config } }
      const keys = Object.keys(parsed)
      if (keys.length === 0) {
        setJsonError("Empty configuration")
        return
      }

      // Use first key as server name
      const serverName = keys[0]
      const cfg = parsed[serverName] as Record<string, unknown>

      if (!cfg || typeof cfg !== "object") {
        setJsonError("Invalid configuration format")
        return
      }

      // Determine type (default to stdio)
      const type = (cfg.type as string) || "stdio"
      if (!["stdio", "http"].includes(type)) {
        setJsonError("Invalid 'type' (must be 'stdio' or 'http')")
        return
      }

      if (type === "stdio" && !cfg.command) {
        setJsonError("stdio type requires 'command' field")
        return
      }

      if (type === "http" && !cfg.url) {
        setJsonError("http type requires 'url' field")
        return
      }

      // Build ServerConfig
      const serverConfig: ServerConfig = {
        type: type as "stdio" | "http",
        command: cfg.command as string | undefined,
        args: cfg.args as string[] | undefined,
        env: cfg.env as Record<string, string> | undefined,
        url: cfg.url as string | undefined,
        headers: cfg.headers as Record<string, string> | undefined,
        enabled: (cfg.enabled as boolean) !== false,
      }

      setJsonError(null)
      onSave(serverName, serverConfig)
      handleClose()
    } catch (e) {
      setJsonError(`Invalid JSON: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const isValid = name.trim() && (
    (config.type === "stdio" && config.command) ||
    (config.type === "http" && config.url)
  )

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
        className={`relative bg-slate-800 rounded-xl shadow-2xl max-w-xl w-full mx-4 max-h-[90vh] overflow-hidden border border-slate-700 transform transition-transform duration-150 ${
          isClosing ? "scale-95" : "scale-100"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h3 className="text-lg font-semibold text-white">
            {serverName ? `Edit Server: ${serverName}` : "Add New Server"}
          </h3>
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Mode Tabs */}
        {!serverName && (
          <div className="flex border-b border-slate-700">
            <button
              onClick={() => setInputMode("form")}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                inputMode === "form"
                  ? "text-blue-400 border-b-2 border-blue-400 bg-slate-900/50"
                  : "text-slate-400 hover:text-slate-300"
              }`}
            >
              Form
            </button>
            <button
              onClick={() => setInputMode("json")}
              className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                inputMode === "json"
                  ? "text-blue-400 border-b-2 border-blue-400 bg-slate-900/50"
                  : "text-slate-400 hover:text-slate-300"
              }`}
            >
              JSON
            </button>
          </div>
        )}

        {/* Content */}
        <div className="p-4 overflow-auto max-h-[calc(90vh-180px)] space-y-4">
          {inputMode === "json" && !serverName ? (
            /* JSON Input Mode */
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Server Configuration (JSON)
                </label>
                <textarea
                  className="input min-h-48 font-mono text-sm"
                  value={jsonText}
                  onChange={(e) => {
                    setJsonText(e.target.value)
                    setJsonError(null)
                  }}
                  placeholder={`// Paste mcpServers config directly:
{
  "vibe_kanban": {
    "command": "npx",
    "args": ["-y", "vibe-kanban@latest", "--mcp"]
  }
}

// Multiple servers:
{
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
  },
  "time": {
    "command": "uvx",
    "args": ["mcp-server-time"]
  }
}`}
                />
              </div>

              {jsonError && (
                <div className="p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300 text-sm">
                  {jsonError}
                </div>
              )}

              <div className="p-3 bg-slate-900 rounded-lg text-xs text-slate-400">
                <p className="font-medium text-slate-300 mb-1">Format:</p>
                <p className="mb-2">Paste your mcpServers config directly. Server name is auto-detected from the key.</p>
                <p className="font-medium text-slate-300 mb-1">Config Fields:</p>
                <ul className="list-disc list-inside space-y-0.5">
                  <li><code className="text-blue-300">command</code> - Command for stdio type</li>
                  <li><code className="text-blue-300">args</code> - Array of arguments</li>
                  <li><code className="text-blue-300">type</code> - "stdio" or "http" (default: stdio)</li>
                  <li><code className="text-blue-300">url</code> - URL for http type</li>
                  <li><code className="text-blue-300">headers</code> - HTTP headers object</li>
                  <li><code className="text-blue-300">env</code> - Environment variables</li>
                  <li><code className="text-blue-300">enabled</code> - Enable/disable (default: true)</li>
                </ul>
              </div>
            </div>
          ) : (
            /* Form Input Mode */
            <>
              {/* Server Name */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Server Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-server"
                  disabled={!!serverName} // Can't rename existing server
                />
              </div>

              {/* Type Selection */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Transport Type
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="type"
                      checked={config.type === "stdio"}
                      onChange={() => setConfig({ ...config, type: "stdio" })}
                    />
                    <span className="text-slate-300">stdio</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="type"
                      checked={config.type === "http"}
                      onChange={() => setConfig({ ...config, type: "http" })}
                    />
                    <span className="text-slate-300">http</span>
                  </label>
                </div>
              </div>

              {/* stdio fields */}
              {config.type === "stdio" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Command <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={config.command || ""}
                      onChange={(e) => setConfig({ ...config, command: e.target.value })}
                      placeholder="npx"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Arguments
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={argsText}
                      onChange={(e) => setArgsText(e.target.value)}
                      placeholder="-y @modelcontextprotocol/server-filesystem /tmp"
                    />
                    <p className="text-xs text-slate-500 mt-1">Space-separated arguments</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Environment Variables
                    </label>
                    <KeyValueEditor rows={envRows} onChange={setEnvRows} />
                  </div>
                </>
              )}

              {/* http fields */}
              {config.type === "http" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      URL <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={config.url || ""}
                      onChange={(e) => setConfig({ ...config, url: e.target.value })}
                      placeholder="http://localhost:3000/mcp"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1">
                      Headers
                    </label>
                    <KeyValueEditor rows={headerRows} onChange={setHeaderRows} />
                  </div>
                </>
              )}

              {/* Enabled */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="toggle"
                  checked={config.enabled}
                  onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
                />
                <span className="text-slate-300">Enabled</span>
              </label>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-700 bg-slate-900/50">
          <div>
            {onDelete && (
              <button
                onClick={() => {
                  onDelete()
                  handleClose()
                }}
                className="px-3 py-1.5 rounded-lg text-sm bg-red-600 hover:bg-red-700 text-white transition-colors"
              >
                Delete Server
              </button>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleClose}
              className="px-4 py-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={inputMode === "json" ? handleJsonSave : handleSave}
              disabled={inputMode === "form" && !isValid}
              className={`px-4 py-2 rounded-lg text-white transition-colors ${
                inputMode === "json"
                  ? "bg-blue-600 hover:bg-blue-700"
                  : isValid
                  ? "bg-blue-600 hover:bg-blue-700"
                  : "bg-slate-700 text-slate-500 cursor-not-allowed"
              }`}
            >
              {serverName ? "Save Changes" : "Add Server"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function KeyValueEditor({
  rows,
  onChange,
}: {
  rows: [string, string][]
  onChange: (rows: [string, string][]) => void
}) {
  const addRow = () => {
    onChange([...rows, ["", ""]])
  }

  const updateRow = (index: number, key: string, value: string) => {
    const newRows = [...rows]
    newRows[index] = [key, value]
    onChange(newRows)
  }

  const removeRow = (index: number) => {
    onChange(rows.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-2">
      {rows.map(([key, value], index) => (
        <div key={index} className="flex gap-2">
          <input
            type="text"
            className="input flex-1"
            value={key}
            onChange={(e) => updateRow(index, e.target.value, value)}
            placeholder="Key"
          />
          <input
            type="text"
            className="input flex-1"
            value={value}
            onChange={(e) => updateRow(index, key, e.target.value)}
            placeholder="Value"
          />
          <button
            onClick={() => removeRow(index)}
            className="p-2 text-slate-400 hover:text-red-400 transition-colors"
            aria-label="Remove"
          >
            ✕
          </button>
        </div>
      ))}
      <button
        onClick={addRow}
        className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
      >
        + Add Row
      </button>
    </div>
  )
}
