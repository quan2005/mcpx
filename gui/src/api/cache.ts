/**
 * Simple in-memory cache for API responses.
 * Reduces redundant network requests when navigating between pages.
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
}

class ApiCacheImpl {
  private cache = new Map<string, CacheEntry<unknown>>()
  private defaultTtl: number

  constructor(defaultTtlMs = 30000) {
    this.defaultTtl = defaultTtlMs
  }

  /**
   * Get cached data or fetch fresh data.
   * @param key Cache key
   * @param fetcher Function to fetch data if not cached
   * @param ttl Time to live in milliseconds (optional, defaults to 30s)
   */
  async get<T>(key: string, fetcher: () => Promise<T>, ttl?: number): Promise<T> {
    const entry = this.cache.get(key) as CacheEntry<T> | undefined
    const effectiveTtl = ttl ?? this.defaultTtl

    if (entry && Date.now() - entry.timestamp < effectiveTtl) {
      return entry.data
    }

    const data = await fetcher()
    this.cache.set(key, { data, timestamp: Date.now() })
    return data
  }

  /**
   * Invalidate cache entries matching a pattern.
   * @param pattern RegExp pattern to match keys (optional, clears all if not provided)
   */
  invalidate(pattern?: RegExp): void {
    if (!pattern) {
      this.cache.clear()
      return
    }

    for (const key of this.cache.keys()) {
      if (pattern.test(key)) {
        this.cache.delete(key)
      }
    }
  }

  /**
   * Get cache statistics.
   */
  stats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys()),
    }
  }
}

export const apiCache = new ApiCacheImpl()
