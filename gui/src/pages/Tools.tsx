import { useEffect, useState } from "react"
import type { Tool } from "../api/client"
import { api } from "../api/client"

export default function Tools() {
  const [tools, setTools] = useState<Tool[]>([])
  const [filter, setFilter] = useState("")
  const [serverFilter, setServerFilter] = useState("")
  const [servers, setServers] = useState<string[]>([])
  const [loading, setLoading] = useState<string | null>(null)

  const loadTools = async () => {
    const data = await api.listTools(serverFilter || undefined)
    setTools(data.tools)

    // Extract unique servers
    const uniqueServers = [...new Set(data.tools.map((t) => t.server))]
    setServers(uniqueServers)
  }

  useEffect(() => {
    loadTools()
  }, [serverFilter])

  const handleToggle = async (server: string, name: string) => {
    const toolKey = `${server}.${name}`
    setLoading(toolKey)
    try {
      await api.toggleTool(server, name)
      await loadTools()
    } finally {
      setLoading(null)
    }
  }

  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(filter.toLowerCase()) ||
      tool.description.toLowerCase().includes(filter.toLowerCase())
  )

  // Group by server
  const groupedTools = filteredTools.reduce((acc, tool) => {
    if (!acc[tool.server]) acc[tool.server] = []
    acc[tool.server].push(tool)
    return acc
  }, {} as Record<string, Tool[]>)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-white">Tools</h2>
        <p className="text-slate-400">Manage and explore available tools</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <input
          type="text"
          placeholder="Search tools..."
          className="input max-w-md"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select
          className="input max-w-xs"
          value={serverFilter}
          onChange={(e) => setServerFilter(e.target.value)}
        >
          <option value="">All Servers</option>
          {servers.map((server) => (
            <option key={server} value={server}>
              {server}
            </option>
          ))}
        </select>
      </div>

      {/* Tools List */}
      <div className="space-y-6">
        {Object.entries(groupedTools).length === 0 ? (
          <div className="card text-center py-12">
            <p className="text-slate-500">No tools found</p>
          </div>
        ) : (
          Object.entries(groupedTools).map(([server, serverTools]) => (
            <div key={server} className="card">
              <h3 className="text-lg font-semibold text-white mb-4">{server}</h3>
              <div className="space-y-3">
                {serverTools.map((tool) => (
                  <div
                    key={`${tool.server}.${tool.name}`}
                    className="flex items-center justify-between p-3 bg-slate-900 rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{tool.name}</span>
                        {!tool.enabled && (
                          <span className="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-400">
                            Disabled
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-400 mt-1">{tool.description}</p>
                    </div>
                    <label className="flex items-center gap-2 cursor-pointer ml-4">
                      <input
                        type="checkbox"
                        className="toggle"
                        checked={tool.enabled}
                        onChange={() => handleToggle(tool.server, tool.name)}
                        disabled={loading === `${tool.server}.${tool.name}`}
                      />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
