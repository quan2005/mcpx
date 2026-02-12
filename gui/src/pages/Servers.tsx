import { useEffect, useState } from "react"
import type { Config, Server } from "../api/client"
import { api } from "../api/client"
import { useConfirmDialog } from "../components/ConfirmDialog"
import { ServerEditor, type ServerConfig } from "../components/ServerEditor"
import { useToast } from "../contexts/ToastContext"

export default function Servers() {
  const [servers, setServers] = useState<Server[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [showEditor, setShowEditor] = useState(false)
  const [editingServer, setEditingServer] = useState<{ name: string; config: ServerConfig } | null>(null)
  const [config, setConfig] = useState<Config | null>(null)
  const { showToast } = useToast()
  const { confirm, dialog } = useConfirmDialog()

  const loadServers = async () => {
    const data = await api.listServers()
    setServers(data.servers)
  }

  const loadConfig = async () => {
    const data = await api.getConfig()
    setConfig(data)
  }

  useEffect(() => {
    loadServers()
    loadConfig()
    const interval = setInterval(loadServers, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleToggle = async (name: string) => {
    setLoading(name)
    try {
      const result = await api.toggleServer(name)
      await loadServers()
      showToast({
        type: result.enabled ? "success" : "warning",
        message: `Server "${name}" ${result.enabled ? "enabled" : "disabled"}`,
      })
    } catch (err) {
      showToast({ type: "error", message: `Failed to toggle server: ${err}` })
    } finally {
      setLoading(null)
    }
  }

  const handleDelete = async (name: string) => {
    const confirmed = await confirm({
      title: "Delete Server",
      message: `Are you sure you want to delete "${name}"? This action cannot be undone.`,
      variant: "danger",
      confirmText: "Delete",
    })

    if (!confirmed || !config) return

    try {
      const newConfig = {
        ...config,
        mcpServers: { ...config.mcpServers },
      }
      delete newConfig.mcpServers[name]
      await api.updateConfig(newConfig)

      // 立即刷新本地状态
      setConfig(newConfig)
      setServers(prev => prev.filter(s => s.name !== name))

      showToast({ type: "success", message: `Server "${name}" deleted` })
    } catch (err) {
      showToast({ type: "error", message: `Failed to delete server: ${err}` })
    }
  }

  const handleEdit = async (name: string) => {
    if (!config?.mcpServers[name]) return
    const serverConfig = config.mcpServers[name]
    // Convert to ServerConfig type
    const typedConfig: ServerConfig = {
      type: serverConfig.type as "stdio" | "http",
      command: serverConfig.command,
      args: serverConfig.args,
      env: serverConfig.env,
      url: serverConfig.url,
      headers: serverConfig.headers,
      enabled: serverConfig.enabled,
    }
    setEditingServer({ name, config: typedConfig })
    setShowEditor(true)
  }

  const handleAdd = () => {
    setEditingServer(null)
    setShowEditor(true)
  }

  const handleSaveServer = async (name: string, serverConfig: ServerConfig) => {
    if (!config) return

    try {
      const newConfig = {
        ...config,
        mcpServers: {
          ...config.mcpServers,
          [name]: serverConfig,
        },
      }
      await api.updateConfig(newConfig)

      // 立即刷新本地状态
      setConfig(newConfig)
      // 重新加载服务器列表以获取最新状态（连接状态、工具数量等）
      await loadServers()

      showToast({
        type: "success",
        message: editingServer ? `Server "${name}" updated` : `Server "${name}" added`,
      })
    } catch (err) {
      showToast({ type: "error", message: `Failed to save server: ${err}` })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Servers</h2>
          <p className="text-slate-400">Manage your MCP servers</p>
        </div>
        <button onClick={handleAdd} className="btn btn-primary">
          + Add Server
        </button>
      </div>

      <div className="space-y-4">
        {servers.length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-slate-500">No servers configured</p>
            <button onClick={handleAdd} className="btn btn-primary mt-4">
              Add Your First Server
            </button>
          </div>
        ) : (
          servers.map((server) => (
            <div key={server.name} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="text-lg font-semibold text-white">{server.name}</h3>
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        server.connected
                          ? "bg-green-900 text-green-400"
                          : server.enabled
                          ? "bg-red-900 text-red-400"
                          : "bg-slate-700 text-slate-400"
                      }`}
                    >
                      {server.connected ? "Connected" : server.enabled ? "Disconnected" : "Disabled"}
                    </span>
                  </div>

                  <div className="mt-2 text-sm text-slate-400 space-y-1">
                    <p>Type: {server.type}</p>
                    {server.server_name && <p>Server: {server.server_name}</p>}
                    {server.version && <p>Version: {server.version}</p>}
                    {server.health && (
                      <p>
                        Health:{" "}
                        <span
                          className={
                            server.health.status === "healthy"
                              ? "text-green-400"
                              : server.health.status === "unhealthy"
                              ? "text-red-400"
                              : "text-slate-400"
                          }
                        >
                          {server.health.status}
                        </span>
                      </p>
                    )}
                  </div>

                  <div className="mt-3 flex gap-4 text-sm">
                    <span className="text-slate-500">
                      <span className="text-white">{server.tools_count || 0}</span> tools
                    </span>
                    <span className="text-slate-500">
                      <span className="text-white">{server.resources_count || 0}</span> resources
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <span className="text-sm text-slate-400">
                      {server.enabled ? "Enabled" : "Disabled"}
                    </span>
                    <input
                      type="checkbox"
                      className="toggle"
                      checked={server.enabled}
                      onChange={() => handleToggle(server.name)}
                      disabled={loading === server.name}
                    />
                  </label>
                </div>
              </div>

              {server.instructions && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <p className="text-sm text-slate-400">{server.instructions}</p>
                </div>
              )}

              {/* Action buttons */}
              <div className="mt-4 pt-4 border-t border-slate-700 flex gap-2">
                <button
                  onClick={() => handleEdit(server.name)}
                  className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
                >
                  Edit
                </button>
                <span className="text-slate-600">|</span>
                <button
                  onClick={() => handleDelete(server.name)}
                  className="text-sm text-red-400 hover:text-red-300 transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Server Editor Modal */}
      <ServerEditor
        isOpen={showEditor}
        serverName={editingServer?.name}
        initialConfig={editingServer?.config}
        onSave={handleSaveServer}
        onDelete={editingServer ? () => handleDelete(editingServer.name) : undefined}
        onClose={() => {
          setShowEditor(false)
          setEditingServer(null)
        }}
      />

      {/* Confirm Dialog */}
      {dialog}
    </div>
  )
}
