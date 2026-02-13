import { apiCache } from "./cache"

const API_BASE = "/api"

// Default timeout for API requests (10 seconds)
const DEFAULT_TIMEOUT = 10000
// Default number of retries for failed requests
const DEFAULT_RETRIES = 2

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

export interface McpxTool {
  name: string
  description: string
  input_schema: Record<string, unknown>
  dynamic_description?: string  // 动态生成的工具/资源列表
}

interface FetchOptions extends RequestInit {
  timeout?: number
  retries?: number
  useCache?: boolean
  cacheTtl?: number
}

/**
 * Fetch JSON with timeout, retry, and optional caching.
 */
async function fetchJson<T>(
  url: string,
  options?: FetchOptions
): Promise<T> {
  const {
    timeout = DEFAULT_TIMEOUT,
    retries = DEFAULT_RETRIES,
    useCache = false,
    cacheTtl,
    ...init
  } = options || {}

  const fullUrl = `${API_BASE}${url}`

  // Use cache for GET requests if enabled
  if (useCache && (!init.method || init.method === "GET")) {
    return apiCache.get<T>(
      fullUrl,
      () => fetchWithRetry<T>(fullUrl, init, timeout, retries),
      cacheTtl
    )
  }

  return fetchWithRetry<T>(fullUrl, init, timeout, retries)
}

/**
 * Fetch with timeout and retry logic.
 */
async function fetchWithRetry<T>(
  url: string,
  init: RequestInit | undefined,
  timeout: number,
  retries: number
): Promise<T> {
  let lastError: Error | null = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...init,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...init?.headers,
        },
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: "Unknown error" }))
        throw new Error(error.error || `HTTP ${response.status}`)
      }

      return response.json()
    } catch (e) {
      clearTimeout(timeoutId)
      lastError = e instanceof Error ? e : new Error(String(e))

      // Don't retry on abort or client errors (4xx)
      if (
        lastError.name === "AbortError" ||
        (e instanceof Error && e.message.includes("HTTP 4"))
      ) {
        throw lastError
      }

      // Wait before retrying (exponential backoff)
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 1000 * (attempt + 1)))
      }
    }
  }

  throw lastError || new Error("Request failed after retries")
}

/**
 * Invalidate API cache for specific patterns.
 */
export function invalidateCache(pattern?: RegExp): void {
  apiCache.invalidate(pattern)
}

export const api = {
  // Servers
  listServers: (options?: FetchOptions) =>
    fetchJson<{ servers: Server[] }>("/servers", { useCache: true, ...options }),
  getServer: (name: string, options?: FetchOptions) =>
    fetchJson<ServerDetail>(`/servers/${name}`, options),
  toggleServer: (name: string) =>
    fetchJson<{ name: string; enabled: boolean; connected: boolean }>(
      `/servers/${name}/toggle`,
      { method: "POST" }
    ),

  // Tools
  listTools: (server?: string, options?: FetchOptions) =>
    fetchJson<{ tools: Tool[] }>(
      `/tools${server ? `?server=${server}` : ""}`,
      { useCache: true, ...options }
    ),
  getTool: (server: string, tool: string, options?: FetchOptions) =>
    fetchJson<ToolDetail>(`/tools/${server}/${tool}`, options),
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
  listResources: (server?: string, options?: FetchOptions) =>
    fetchJson<{ resources: Resource[] }>(
      `/resources${server ? `?server=${server}` : ""}`,
      { useCache: true, ...options }
    ),
  readResource: (server: string, uri: string) =>
    fetchJson<{ success: boolean; contents: unknown[] }>("/read", {
      method: "POST",
      body: JSON.stringify({ server, uri }),
    }),

  // Health
  getHealth: (options?: FetchOptions) =>
    fetchJson<HealthStatus>("/health", { useCache: true, cacheTtl: 5000, ...options }),
  getServerHealth: (server: string, options?: FetchOptions) =>
    fetchJson<{
      server_name: string
      status: string
      last_check: string | null
      last_success: string | null
      consecutive_failures: number
      last_error: string | null
    }>(`/health/${server}`, options),
  checkServerHealth: (server: string) =>
    fetchJson<{ server: string; healthy: boolean; status: string }>(
      `/health/${server}/check`,
      { method: "POST" }
    ),

  // Config
  getConfig: (options?: FetchOptions) =>
    fetchJson<Config>("/config", options),
  updateConfig: (config: Partial<Config>) =>
    fetchJson<{ success: boolean; message: string }>("/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),

  // MCPX Tools
  getMcpxTools: (options?: FetchOptions) =>
    fetchJson<{
      tools: McpxTool[]
      tools_description: string
      resources_description: string
    }>("/mcpx-tools", { useCache: true, ...options }),
}
