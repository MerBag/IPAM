import { Command, LoaderCircle, Search, Server, UserRound, Waypoints, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { request, unwrapList } from '../lib/api'
import type { SearchResult } from '../types'
import { EmptyState } from './ui'

function resultRoute(result: SearchResult) {
  const type = (result.entity_type || result.type || '').toLowerCase()
  const value = result.primary || result.address || result.cidr || result.value || result.title || result.label || ''
  if (type?.includes('prefix')) return `/prefixes?search=${encodeURIComponent(value)}`
  if (type?.includes('subnet')) return `/subnets?search=${encodeURIComponent(value)}`
  if (type?.includes('device') || type?.includes('server')) return `/devices?search=${encodeURIComponent(value)}`
  if (type?.includes('customer')) return `/customers?search=${encodeURIComponent(value)}`
  if (type?.includes('router')) return `/routers?search=${encodeURIComponent(value)}`
  return `/ip-addresses?search=${encodeURIComponent(value)}`
}

function ResultIcon({ type }: { type: string }) {
  if (/customer|user/i.test(type)) return <UserRound size={17} />
  if (/device|server|router/i.test(type)) return <Server size={17} />
  return <Waypoints size={17} />
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen(true)
        window.setTimeout(() => inputRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      setLoading(false)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      request<unknown>(`/search?q=${encodeURIComponent(query.trim())}`, { signal: controller.signal })
        .then((payload) => setResults(unwrapList<SearchResult>(payload)))
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === 'AbortError')) setResults([])
        })
        .finally(() => !controller.signal.aborted && setLoading(false))
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const help = useMemo(() => query.trim().length < 2, [query])
  const choose = (result: SearchResult) => {
    navigate(resultRoute(result))
    setOpen(false)
    setQuery('')
  }

  return (
    <div className={`global-search ${open ? 'global-search--open' : ''}`}>
      <Search size={18} className="global-search__icon" aria-hidden="true" />
      <input
        ref={inputRef}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setOpen(false)
            inputRef.current?.blur()
          }
          if (event.key === 'Enter' && results[0]) choose(results[0])
        }}
        placeholder="Search IPs, hostnames, devices…"
        aria-label="Global search"
      />
      {loading ? <LoaderCircle size={16} className="spin global-search__end" /> : query ? (
        <button type="button" className="global-search__clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={15} /></button>
      ) : <kbd><Command size={12} />K</kbd>}
      {open && (
        <>
          <button className="search-scrim" type="button" aria-label="Close search" onClick={() => setOpen(false)} />
          <div className="search-results">
            {help ? (
              <div className="search-help">
                <span>Search across the entire IPAM</span>
                <div><span>IP address</span><span>Hostname</span><span>MAC</span><span>Customer</span></div>
              </div>
            ) : results.length ? (
              <>
                <div className="search-results__label">Results</div>
                {results.slice(0, 8).map((result) => (
                  <button type="button" className="search-result" key={`${result.entity_type || result.type || 'result'}-${result.id}`} onClick={() => choose(result)}>
                    <span className="search-result__icon"><ResultIcon type={result.entity_type || result.type || ''} /></span>
                    <span><strong>{result.primary || result.title || result.label || result.address || result.cidr || result.value}</strong><small>{result.secondary || result.subtitle || result.entity_type || result.type}</small></span>
                    <span className="search-result__type">{result.entity_type || result.type}</span>
                  </button>
                ))}
              </>
            ) : !loading ? <EmptyState icon={Search} title="No matches" description="Try an address, hostname, customer, router, or MAC address." /> : null}
          </div>
        </>
      )}
    </div>
  )
}
