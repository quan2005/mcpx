import { useEffect, useState } from "react"
import type { Config } from "../api/client"
import { api } from "../api/client"
import { useToast } from "../contexts/ToastContext"

export default function Settings() {
  const [config, setConfig] = useState<Config | null>(null)
  const [saving, setSaving] = useState(false)

  const { showToast } = useToast()

  useEffect(() => {
    api.getConfig().then(setConfig)
  }, [])

  const handleSave = async () => {
    if (!config) return

    setSaving(true)

    try {
      await api.updateConfig(config)
      showToast({ type: "success", message: "Configuration saved and reloaded successfully" })
    } catch (err) {
      showToast({ type: "error", message: `Failed to save configuration: ${err}` })
    } finally {
      setSaving(false)
    }
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Settings</h2>
        <p className="text-slate-400">Configure MCPX proxy settings</p>
      </div>

      <div className="space-y-6">
        {/* Health Check Settings */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Health Check</h3>
          <div className="space-y-4">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                className="toggle"
                checked={config.health_check_enabled}
                onChange={(e) =>
                  setConfig({ ...config, health_check_enabled: e.target.checked })
                }
              />
              <span className="text-slate-300">Enable health checks</span>
            </label>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-slate-400 mb-1">
                  Check Interval (seconds)
                </label>
                <input
                  type="number"
                  className="input"
                  value={config.health_check_interval}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      health_check_interval: parseInt(e.target.value) || 30,
                    })
                  }
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">
                  Check Timeout (seconds)
                </label>
                <input
                  type="number"
                  className="input"
                  value={config.health_check_timeout}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      health_check_timeout: parseInt(e.target.value) || 5,
                    })
                  }
                />
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">
                  Failure Threshold
                </label>
                <input
                  type="number"
                  className="input"
                  value={config.health_check_failure_threshold}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      health_check_failure_threshold: parseInt(e.target.value) || 2,
                    })
                  }
                />
              </div>
            </div>
          </div>
        </div>

        {/* Compression Settings */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Compression</h3>
          <div className="space-y-4">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                className="toggle"
                checked={config.toon_compression_enabled}
                onChange={(e) =>
                  setConfig({ ...config, toon_compression_enabled: e.target.checked })
                }
              />
              <span className="text-slate-300">Enable TOON compression</span>
            </label>

            <div>
              <label className="block text-sm text-slate-400 mb-1">
                Minimum Size for Compression
              </label>
              <input
                type="number"
                className="input max-w-xs"
                value={config.toon_compression_min_size}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    toon_compression_min_size: parseInt(e.target.value) || 1,
                  })
                }
              />
            </div>

            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                className="toggle"
                checked={config.schema_compression_enabled}
                onChange={(e) =>
                  setConfig({ ...config, schema_compression_enabled: e.target.checked })
                }
              />
              <span className="text-slate-300">Enable schema compression (TypeScript style)</span>
            </label>
          </div>
        </div>

        {/* Output Settings */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Output</h3>
          <label className="flex items-center gap-3">
            <input
              type="checkbox"
              className="toggle"
              checked={config.include_structured_content}
              onChange={(e) =>
                setConfig({ ...config, include_structured_content: e.target.checked })
              }
            />
            <span className="text-slate-300">Include structured content in responses</span>
          </label>
        </div>

        {/* Servers Configuration */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Servers Configuration</h3>
          <p className="text-sm text-slate-400 mb-4">
            Go to <a href="/servers" className="text-blue-400 hover:underline">Servers</a> page to add, edit, or delete servers.
          </p>
          <pre className="bg-slate-900 p-4 rounded-lg text-sm text-slate-300 overflow-auto max-h-96">
            {JSON.stringify(config.mcpServers, null, 2)}
          </pre>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button onClick={handleSave} disabled={saving} className="btn btn-primary">
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  )
}
