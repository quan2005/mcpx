import { useEffect, useState } from "react";
import type { HealthStatus, McpxTool, Server } from "../api/client";
import { api } from "../api/client";
import { Loading } from "../components/Loading";
import { useToast } from "../contexts/ToastContext";

export default function Dashboard() {
  const [servers, setServers] = useState<Server[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [mcpxTools, setMcpxTools] = useState<McpxTool[]>([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  useEffect(() => {
    const loadData = async () => {
      try {
        const [serversData, healthData, toolsData] = await Promise.all([
          api.listServers(),
          api.getHealth(),
          api.getMcpxTools(),
        ]);
        setServers(serversData.servers);
        setHealth(healthData);
        setMcpxTools(toolsData.tools);
      } catch (error) {
        showToast({
          type: "error",
          message: `Failed to load dashboard data: ${error}`,
        });
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [showToast]);

  if (loading) {
    return <Loading text="Loading dashboard..." />;
  }

  const connectedServers = servers.filter((s) => s.connected);
  const enabledServers = servers.filter((s) => s.enabled);
  const totalTools = servers.reduce((sum, s) => sum + (s.tools_count || 0), 0);
  const totalResources = servers.reduce(
    (sum, s) => sum + (s.resources_count || 0),
    0,
  );

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
            {health?.summary.unhealthy || 0} unhealthy,{" "}
            {health?.summary.unknown || 0} unknown
          </div>
        </div>

        <div className="card">
          <div className="text-sm text-slate-400">Total Tools</div>
          <div className="text-3xl font-bold text-blue-400">{totalTools}</div>
          <div className="text-sm text-slate-500">Across all servers</div>
        </div>

        <div className="card">
          <div className="text-sm text-slate-400">Total Resources</div>
          <div className="text-3xl font-bold text-purple-400">
            {totalResources}
          </div>
          <div className="text-sm text-slate-500">Across all servers</div>
        </div>
      </div>

      {/* MCPX Tools Reference */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">
          MCPX Tools Reference
        </h3>
        <p className="text-sm text-slate-400 mb-4">
          MCPX exposes two unified tools to interact with all your MCP servers:
        </p>

        <div className="space-y-4">
          {mcpxTools.map((tool) => (
            <div key={tool.name} className="bg-slate-900 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    tool.name === "invoke"
                      ? "bg-blue-900 text-blue-300"
                      : "bg-purple-900 text-purple-300"
                  }`}
                >
                  TOOL
                </span>
                <h4 className="text-white font-mono font-semibold">
                  {tool.name}
                </h4>
              </div>

              {/* Tool Description (docstring) */}
              <pre className="text-slate-300 text-sm mb-4 whitespace-pre-wrap font-sans">
                {tool.description}
              </pre>

              {/* Parameters */}
              <div className="mb-4">
                <span className="text-xs text-slate-500 uppercase tracking-wide">
                  Parameters
                </span>
                <div className="mt-1 font-mono text-sm space-y-1">
                  {Object.entries(
                    tool.input_schema.properties as Record<
                      string,
                      { type: string; description?: string }
                    >,
                  ).map(([paramName, paramDef]) => {
                    const required = (
                      tool.input_schema.required as string[]
                    )?.includes(paramName);
                    return (
                      <div key={paramName} className="text-slate-300">
                        <span className="text-yellow-400">{paramName}</span>
                        {!required && <span className="text-slate-500">?</span>}
                        <span className="text-slate-500">
                          : {paramDef.type}
                        </span>
                        {paramDef.description && (
                          <span className="text-slate-400">
                            {" "}
                            — {paramDef.description}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Dynamic Description - the real tool/resource list */}
              {tool.dynamic_description && (
                <div>
                  <span className="text-xs text-slate-500 uppercase tracking-wide">
                    {tool.name === "invoke"
                      ? "Available Tools"
                      : "Available Resources"}
                  </span>
                  <pre className="mt-1 bg-slate-800 p-3 rounded text-sm overflow-x-auto whitespace-pre-wrap text-slate-300">
                    {tool.dynamic_description}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Quick Connect */}
      <div className="card">
        <h3 className="text-lg font-semibold text-white mb-4">Quick Connect</h3>
        <p className="text-sm text-slate-400 mb-2">
          Add MCPX to your Claude Code configuration:
        </p>
        <div className="bg-slate-900 p-4 rounded-lg font-mono text-sm text-slate-300 overflow-x-auto">
          <pre>
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
                  <span className="text-xs text-slate-500">
                    ({server.type})
                  </span>
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
  );
}
