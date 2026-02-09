const API_BASE = "/api"

export interface Server {
  name: string
  enabled: boolean
  type: string
  connected: boolean
  server_name?: string
  version?: string
  instructions?: string
  health?: {
    status: string
    last_check: string | null
    consecutive_failures: number
  }
  tools_count?: number
  resources_count?: number
}

export interface ServerDetail extends Server {
  config: {
    command: string | null
    args: string[]
    env: Record<string, string> | null
    url: string | null
    headers: Record<string, string> | null
  }
  health?: {
    status: string
    last_check: string | null
    last_success: string | null
    consecutive_failures: number
    last_error: string | null
  }
}

export interface Tool {
  server: string
  name: string
  description: string
  enabled: boolean
}

export interface ToolDetail extends Tool {
  input_schema: Record<string, unknown>
}

export interface Resource {
  server: string
  uri: string
  name: string
  description: string | null
  mime_type: string | null
  size: number | null
}

export interface HealthStatus {
  summary: {
    total: number
    healthy: number
    unhealthy: number
    unknown: number
  }
  servers: Record<string, {
    status: string
    last_check: string | null
    last_success: string | null
    consecutive_failures: number
    last_error: string | null
  }>
}

export interface Config {
  mcpServers: Record<string, {
    type: string
    command?: string
    args?: string[]
    env?: Record<string, string>
    url?: string
    headers?: Record<string, string>
    enabled: boolean
  }>
  disabled_tools: string[]
  health_check_enabled: boolean
  health_check_interval: number
  health_check_timeout: number
  health_check_failure_threshold: number
  toon_compression_enabled: boolean
  toon_compression_min_size: number
  schema_compression_enabled: boolean
  include_structured_content: boolean
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "Unknown error" }))
    throw new Error(error.error || `HTTP ${response.status}`)
  }

  return response.json()
}

export const api = {
  // Servers
  listServers: () => fetchJson<{ servers: Server[] }>("/servers"),
  getServer: (name: string) => fetchJson<ServerDetail>(`/servers/${name}`),
  toggleServer: (name: string) =>
    fetchJson<{ name: string; enabled: boolean; connected: boolean }>(
      `/servers/${name}/toggle`,
      { method: "POST" }
    ),

  // Tools
  listTools: (server?: string) =>
    fetchJson<{ tools: Tool[] }>(`/tools${server ? `?server=${server}` : ""}`),
  getTool: (server: string, tool: string) =>
    fetchJson<ToolDetail>(`/tools/${server}/${tool}`),
  toggleTool: (server: string, tool: string) =>
    fetchJson<{ server: string; name: string; enabled: boolean }>(
      `/tools/${server}/${tool}/toggle`,
      { method: "POST" }
    ),
  invokeTool: (method: string, arguments_?: Record<string, unknown>) =>
    fetchJson<{ success: boolean; data: unknown; compressed: boolean }>("/invoke", {
      method: "POST",
      body: JSON.stringify({ method, arguments: arguments_ }),
    }),

  // Resources
  listResources: (server?: string) =>
    fetchJson<{ resources: Resource[] }>(`/resources${server ? `?server=${server}` : ""}`),
  readResource: (server: string, uri: string) =>
    fetchJson<{ success: boolean; contents: unknown[] }>("/read", {
      method: "POST",
      body: JSON.stringify({ server, uri }),
    }),

  // Health
  getHealth: () => fetchJson<HealthStatus>("/health"),
  getServerHealth: (server: string) =>
    fetchJson<{
      server_name: string
      status: string
      last_check: string | null
      last_success: string | null
      consecutive_failures: number
      last_error: string | null
    }>(`/health/${server}`),
  checkServerHealth: (server: string) =>
    fetchJson<{ server: string; healthy: boolean; status: string }>(
      `/health/${server}/check`,
      { method: "POST" }
    ),

  // Config
  getConfig: () => fetchJson<Config>("/config"),
  updateConfig: (config: Partial<Config>) =>
    fetchJson<{ success: boolean; message: string }>("/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),
}
