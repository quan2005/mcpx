import { useEffect, useState } from "react"
import type { HealthStatus, Server } from "../api/client"
import { api } from "../api/client"

export default function Dashboard() {
  const [servers, setServers] = useState<Server[]>([])
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      try {
        const [serversData, healthData] = await Promise.all([
          api.listServers(),
          api.getHealth(),
        ])
        setServers(serversData.servers)
        setHealth(healthData)
      } catch (error) {
        console.error("Failed to load dashboard data:", error)
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading...</div>
      </div>
    )
  }

  const connectedServers = servers.filter((s) => s.connected)
  const enabledServers = servers.filter((s) => s.enabled)
  const totalTools = servers.reduce((sum, s) => sum + (s.tools_count || 0), 0)
  const totalResources = servers.reduce((sum, s) => sum + (s.resources_count || 0), 0)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Dashboard</h2>
        <p className="text-slate-400">Overview of your MCP servers</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="text-sm text-slate-400">Total Servers</div>
          <div className="text-3xl font-bold text-white">{servers.length}</div>
          <div className="text-sm text-slate-500">
            {enabledServers.length} enabled, {connectedServers.length} connected
          </div>
        </div>

        <div className="card">
          <div className="text-sm text-slate-400">Health Status</div>
          <div className="text-3xl font-bold text-green-400">
            {health?.summary.healthy || 0}
          </div>
          <div className="text-sm text-slate-500">
            {health?.summary.unhealthy || 0} unhealthy, {health?.summary.unknown || 0} unknown
          </div>
        </div>

        <div className="card">
          <div className="text-sm text-slate-400">Total Tools</div>
          <div className="text-3xl font-bold text-blue-400">{totalTools}</div>
          <div className="text-sm text-slate-500">Across all servers</div>
        </div>

        <div className="card">
          <div className="text-sm text-slate-400">Total Resources</div>
          <div className="text-3xl font-bold text-purple-400">{totalResources}</div>
          <div className="text-sm text-slate-500">Across all servers</div>
        </div>
      </div>

      {/* Quick Connect */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Quick Connect</h3>
        <div className="bg-slate-900 p-4 rounded-lg font-mono text-sm text-slate-300 overflow-x-auto">
          <p className="text-slate-500 mb-2"># Connect via MCP Inspector</p>
          <p>npx @anthropic-ai/mcp-inspector</p>
          <p className="text-slate-500 mt-4 mb-2"># Or use with Claude Desktop</p>
          <p>Add to ~/Library/Application Support/Claude/claude_desktop_config.json:</p>
          <pre className="mt-2 text-blue-300">
{`{
  "mcpServers": {
    "mcpx": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}`}
          </pre>
        </div>
      </div>

      {/* Server Status */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Server Status</h3>
        {servers.length === 0 ? (
          <p className="text-slate-500">No servers configured</p>
        ) : (
          <div className="space-y-2">
            {servers.map((server) => (
              <div
                key={server.name}
                className="flex items-center justify-between p-3 bg-slate-900 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      server.connected
                        ? "bg-green-500"
                        : server.enabled
                        ? "bg-red-500"
                        : "bg-slate-500"
                    }`}
                  />
                  <span className="text-white font-medium">{server.name}</span>
                  <span className="text-xs text-slate-500">({server.type})</span>
                </div>
                <div className="flex items-center gap-4 text-sm text-slate-400">
                  <span>{server.tools_count || 0} tools</span>
                  <span>{server.resources_count || 0} resources</span>
                  {server.health && (
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        server.health.status === "healthy"
                          ? "bg-green-900 text-green-400"
                          : server.health.status === "unhealthy"
                          ? "bg-red-900 text-red-400"
                          : "bg-slate-700 text-slate-400"
                      }`}
                    >
                      {server.health.status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
