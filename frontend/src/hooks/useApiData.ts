import { useCallback, useEffect, useState } from 'react'
import { request } from '../lib/api'

export function useApiData<T>(path: string | null, initial: T) {
  const [data, setData] = useState<T>(initial)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)

  const reload = useCallback(() => setRevision((value) => value + 1), [])

  useEffect(() => {
    if (!path) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setError('')
    request<T>(path, { signal: controller.signal })
      .then((result) => setData(result))
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setError(reason instanceof Error ? reason.message : 'Unable to load data.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [path, revision])

  return { data, setData, loading, error, reload }
}
