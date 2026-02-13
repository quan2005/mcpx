import { useCallback, useEffect, useState } from "react"

interface UseAsyncDataResult<T> {
  data: T | null
  loading: boolean
  error: Error | null
  refresh: () => void
}

/**
 * Generic hook for async data fetching with loading/error states.
 * Eliminates repetitive loading logic across pages.
 */
export function useAsyncData<T>(
  fetchFn: () => Promise<T>,
  deps: unknown[] = []
): UseAsyncDataResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchFn()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    load()
  }, [load])

  return { data, loading, error, refresh: load }
}
