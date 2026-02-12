import { useState } from "react"
import { api } from "../api/client"

interface ToolTesterProps {
  server: string
  tool: string
  schema: Record<string, unknown>
  enabled: boolean
}

interface SchemaProperty {
  type: string
  description?: string
  enum?: string[]
  default?: unknown
  items?: SchemaProperty
  properties?: Record<string, SchemaProperty>
  required?: string[]
}

export function ToolTester({ server, tool, schema, enabled }: ToolTesterProps) {
  const [params, setParams] = useState<Record<string, unknown>>({})
  const [result, setResult] = useState<{
    success: boolean
    data: unknown
    compressed: boolean
    error?: string
  } | null>(null)
  const [loading, setLoading] = useState(false)

  const properties =
    (schema?.properties as Record<string, SchemaProperty> | undefined) || {}
  const required = (schema?.required as string[] | undefined) || []

  const handleParamChange = (key: string, value: unknown) => {
    setParams((prev) => ({ ...prev, [key]: value }))
  }

  const handleTest = async () => {
    setLoading(true)
    setResult(null)

    try {
      const response = await api.invokeTool(`${server}.${tool}`, params)
      setResult(response)
    } catch (err) {
      setResult({
        success: false,
        data: null,
        compressed: false,
        error: String(err),
      })
    } finally {
      setLoading(false)
    }
  }

  const renderParamInput = (key: string, prop: SchemaProperty) => {
    const isRequired = required.includes(key)
    const value = params[key]

    switch (prop.type) {
      case "string":
        if (prop.enum) {
          return (
            <select
              className="input"
              value={(value as string) || ""}
              onChange={(e) => handleParamChange(key, e.target.value)}
              required={isRequired}
            >
              <option value="">Select...</option>
              {prop.enum.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          )
        }
        return (
          <input
            type="text"
            className="input"
            value={(value as string) || ""}
            onChange={(e) => handleParamChange(key, e.target.value)}
            placeholder={prop.description || key}
            required={isRequired}
          />
        )

      case "number":
      case "integer":
        return (
          <input
            type="number"
            className="input"
            value={(value as number) ?? ""}
            onChange={(e) =>
              handleParamChange(key, e.target.value ? Number(e.target.value) : undefined)
            }
            placeholder={prop.description || key}
            required={isRequired}
          />
        )

      case "boolean":
        return (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="toggle"
              checked={(value as boolean) || false}
              onChange={(e) => handleParamChange(key, e.target.checked)}
            />
            <span className="text-sm text-slate-400">
              {(value as boolean) ? "true" : "false"}
            </span>
          </label>
        )

      case "array":
        return (
          <div className="space-y-2">
            <textarea
              className="input min-h-20"
              value={Array.isArray(value) ? JSON.stringify(value) : ""}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value)
                  handleParamChange(key, parsed)
                } catch {
                  // Keep invalid JSON as-is for user to fix
                }
              }}
              placeholder={prop.description || "JSON array"}
              required={isRequired}
            />
            {prop.items && (
              <p className="text-xs text-slate-500">
                Items: {prop.items.type || JSON.stringify(prop.items)}
              </p>
            )}
          </div>
        )

      case "object":
        return (
          <div className="space-y-2">
            <textarea
              className="input min-h-20"
              value={typeof value === "object" && value !== null ? JSON.stringify(value, null, 2) : ""}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value)
                  handleParamChange(key, parsed)
                } catch {
                  // Keep invalid JSON as-is for user to fix
                }
              }}
              placeholder={prop.description || "JSON object"}
              required={isRequired}
            />
          </div>
        )

      default:
        return (
          <input
            type="text"
            className="input"
            value={(value as string) || ""}
            onChange={(e) => handleParamChange(key, e.target.value)}
            placeholder={`${prop.type} (as string)`}
            required={isRequired}
          />
        )
    }
  }

  const paramKeys = Object.keys(properties)
  const missingRequired = required.filter((k) => params[k] === undefined || params[k] === "")

  if (!enabled) {
    return (
      <div className="p-4 bg-slate-900 rounded-lg text-center text-slate-400">
        Tool is disabled. Enable it to test.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Parameters */}
      {paramKeys.length > 0 && (
        <div className="space-y-3">
          {paramKeys.map((key) => {
            const prop = properties[key]
            const isRequired = required.includes(key)

            return (
              <div key={key}>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  {key}
                  {isRequired && <span className="text-red-400 ml-1">*</span>}
                  {prop.description && (
                    <span className="text-slate-500 font-normal ml-2">- {prop.description}</span>
                  )}
                </label>
                {renderParamInput(key, prop)}
              </div>
            )
          })}
        </div>
      )}

      {paramKeys.length === 0 && (
        <p className="text-sm text-slate-400">This tool takes no parameters.</p>
      )}

      {/* Test Button */}
      <button
        onClick={handleTest}
        disabled={loading || missingRequired.length > 0}
        className="btn btn-primary"
      >
        {loading ? "Running..." : "Run Tool"}
      </button>

      {missingRequired.length > 0 && (
        <p className="text-sm text-red-400">
          Missing required: {missingRequired.join(", ")}
        </p>
      )}

      {/* Result */}
      {result && (
        <div
          className={`p-3 rounded-lg ${
            result.success ? "bg-green-900/30 border border-green-700" : "bg-red-900/30 border border-red-700"
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className={`text-sm font-medium ${result.success ? "text-green-400" : "text-red-400"}`}>
              {result.success ? "Success" : "Error"}
            </span>
            {result.compressed && (
              <span className="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-400">
                Compressed
              </span>
            )}
          </div>
          {result.error ? (
            <p className="text-red-300 text-sm">{result.error}</p>
          ) : (
            <pre className="text-sm text-slate-300 overflow-auto max-h-64">
              {JSON.stringify(result.data, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
