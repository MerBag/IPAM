import { ArrowLeft, Check, ChevronsUpDown, Grid3X3, Network, Plus, RefreshCw, Search, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Badge, Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, ProgressBar, Select, StatusBadge } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useApiData } from '../hooks/useApiData'
import { request, unwrapList } from '../lib/api'
import { formatNumber, formatPercent, percentValue } from '../lib/format'
import type { IpAddress, Prefix, Subnet } from '../types'

function networkSize(cidr?: string) {
  const length = Number(cidr?.split('/')[1])
  return Number.isFinite(length) ? 2 ** (32 - length) : undefined
}

function ipv4Number(address: string) {
  return address.split('.').reduce((value, octet) => value * 256 + Number(octet), 0)
}

function ipv4Text(value: number) {
  return [24, 16, 8, 0].map((shift) => Math.floor(value / 2 ** shift) % 256).join('.')
}

const ACTIVE_ADDRESS_STATUSES = new Set(['assigned', 'reserved', 'gateway', 'blackholed'])

function addressValue(address: IpAddress) {
  return ipv4Number(address.address || address.ip_address || '')
}

function isActiveAddress(address: IpAddress) {
  return ACTIVE_ADDRESS_STATUSES.has(String(address.status).toLowerCase())
}

function calculatedSubnet(cidr: string, actualAddresses: IpAddress[] = []): Subnet {
  const [address, lengthText] = cidr.split('/')
  const prefixLength = Number(lengthText)
  const total = 2 ** (32 - prefixLength)
  const network = Math.floor(ipv4Number(address) / total) * total
  const broadcast = network + total - 1
  const unavailable = new Set<number>()
  if (prefixLength <= 30) {
    unavailable.add(network)
    unavailable.add(broadcast)
  }
  actualAddresses.forEach((actual) => {
    const value = addressValue(actual)
    if (value >= network && value <= broadcast && isActiveAddress(actual)) unavailable.add(value)
  })
  const used = unavailable.size
  return {
    cidr,
    network_address: ipv4Text(network),
    broadcast_address: ipv4Text(broadcast),
    prefix_length: prefixLength,
    first_usable_ip: ipv4Text(network + (prefixLength <= 30 ? 1 : 0)),
    last_usable_ip: ipv4Text(network + total - 1 - (prefixLength <= 30 ? 1 : 0)),
    total_addresses: total,
    used_addresses: used,
    free_addresses: total - used,
    utilization_percent: (used / total) * 100,
    status: 'free',
  }
}

function calculatedAddresses(cidr: string, actualAddresses: IpAddress[] = []): IpAddress[] {
  const subnet = calculatedSubnet(cidr, actualAddresses)
  const total = subnet.total_addresses || 0
  const start = ipv4Number(subnet.network_address || '0.0.0.0')
  const actualByValue = new Map(actualAddresses.map((actual) => [addressValue(actual), actual]))
  return Array.from({ length: Math.min(total, 64) }, (_, index) => {
    const value = start + index
    const actual = actualByValue.get(value)
    const calculatedStatus = subnet.prefix_length !== undefined && subnet.prefix_length <= 30 && index === 0
      ? 'network'
      : subnet.prefix_length !== undefined && subnet.prefix_length <= 30 && index === total - 1
        ? 'broadcast'
        : 'free'
    return {
      ...(actual && isActiveAddress(actual) ? actual : {}),
      id: actual && isActiveAddress(actual) ? actual.id : `preview-${cidr}-${index}`,
      address: ipv4Text(value),
      status: actual && isActiveAddress(actual) ? actual.status : calculatedStatus,
    }
  })
}

export function SubnetsPage() {
  const [params, setParams] = useSearchParams()
  const { data: prefixData, loading: prefixesLoading } = useApiData<unknown>('/prefixes', [])
  const { data: subnetData, loading: subnetsLoading, error: subnetError, reload: reloadSubnets } = useApiData<unknown>('/subnets?limit=2000', [])
  const prefixes = unwrapList<Prefix>(prefixData)
  const existingSubnets = unwrapList<Subnet>(subnetData)
  const search = (params.get('search') || '').trim().toLowerCase()
  const searchedSubnet = search ? existingSubnets.find((subnet) => subnet.cidr.toLowerCase().includes(search)) : undefined
  const selectedPrefixId = params.get('prefix') || (searchedSubnet?.prefix_id ? String(searchedSubnet.prefix_id) : '') || (prefixes[0] ? String(prefixes[0].id) : '')
  const selectedPrefix = prefixes.find((prefix) => String(prefix.id) === selectedPrefixId)
  const baseLength = Number(selectedPrefix?.cidr.split('/')[1] || 24)
  // Keep the visual grid bounded to 1,024 blocks. The API can support larger
  // programmatic splits without forcing thousands of buttons into the browser.
  const maxPreviewLength = Math.min(32, baseLength + 10)
  const [prefixLength, setPrefixLength] = useState(29)
  const [selectedSubnet, setSelectedSubnet] = useState<Subnet | null>(null)
  const [creating, setCreating] = useState(false)
  const [findingNext, setFindingNext] = useState(false)
  const [allocatingNext, setAllocatingNext] = useState(false)
  const [splitting, setSplitting] = useState(false)
  const [childPrefixLength, setChildPrefixLength] = useState(30)
  const { notify } = useToast()
  const { user } = useAuth()
  const readOnly = user?.role === 'read_only'

  useEffect(() => {
    if (!selectedPrefixId && prefixes[0]) setParams({ prefix: String(prefixes[0].id) }, { replace: true })
  }, [prefixes, selectedPrefixId, setParams])
  useEffect(() => {
    setSelectedSubnet(null)
  }, [selectedPrefixId])
  useEffect(() => {
    if (!selectedPrefix) return
    if (baseLength >= 32) {
      if (prefixLength !== 32) setPrefixLength(32)
      return
    }
    if (prefixLength <= baseLength || prefixLength > maxPreviewLength) {
      setPrefixLength(Math.min(maxPreviewLength, Math.max(baseLength + 1, 29)))
    }
  }, [selectedPrefix?.id, baseLength, maxPreviewLength, prefixLength])
  useEffect(() => {
    if (!searchedSubnet) return
    const searchedLength = Number(searchedSubnet.cidr.split('/')[1])
    if (Number.isFinite(searchedLength)) setPrefixLength(searchedLength)
    setSelectedSubnet(searchedSubnet)
  }, [searchedSubnet?.id, searchedSubnet?.cidr])
  useEffect(() => {
    if (!selectedSubnet?.cidr) return
    const selectedLength = Number(selectedSubnet.cidr.split('/')[1])
    if (Number.isFinite(selectedLength)) setChildPrefixLength(Math.min(32, selectedLength + 1))
  }, [selectedSubnet?.cidr])

  const prefixAddressPath = selectedPrefix ? `/ip-addresses?prefix_id=${selectedPrefix.id}&limit=2000` : null
  const { data: prefixAddressData, loading: prefixAddressesLoading, error: prefixAddressError, reload: reloadPrefixAddresses } = useApiData<unknown>(prefixAddressPath, [])
  const prefixAddresses = unwrapList<IpAddress>(prefixAddressData)
  const previewPath = selectedPrefix && baseLength < 32 && prefixLength > baseLength && prefixLength <= maxPreviewLength
    ? `/prefixes/${selectedPrefix.id}/split-preview?new_prefix_length=${prefixLength}`
    : null
  const { data: previewData, loading: previewLoading, error: previewError, reload: reloadPreview } = useApiData<unknown>(previewPath, [])
  const preview = unwrapList<string>(previewData).map((cidr) => calculatedSubnet(cidr, prefixAddresses))
  const blocks = useMemo(() => {
    const source = preview.length ? preview : existingSubnets.filter((subnet) => !selectedPrefix || String(subnet.prefix_id) === String(selectedPrefix.id))
    return source.map((block) => {
      const existing = existingSubnets.find((subnet) => subnet.cidr === block.cidr)
      return existing ? { ...block, ...existing } : block
    })
  }, [preview, existingSubnets, selectedPrefix])

  const addressPath = selectedSubnet?.id ? `/ip-addresses?subnet_id=${selectedSubnet.id}&limit=2000` : null
  const { data: addressData, loading: addressesLoading, error: addressError } = useApiData<unknown>(addressPath, [])
  const addresses = unwrapList<IpAddress>(addressData)
  const createSubnets = async () => {
    if (!selectedPrefix) return
    setCreating(true)
    try {
      await request(`/prefixes/${selectedPrefix.id}/split`, { method: 'POST', body: { new_prefix_length: prefixLength } })
      notify(`Created /${prefixLength} subnets inside ${selectedPrefix.cidr}.`)
      reloadSubnets()
      reloadPreview()
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : 'Unable to create subnets.', 'error')
    } finally {
      setCreating(false)
    }
  }

  const findNextSubnet = async () => {
    if (!selectedPrefix) return
    setFindingNext(true)
    try {
      const candidate = await request<{ cidr: string; subnet_id?: number | null; already_materialized?: boolean }>(`/subnets/next-available?prefix_id=${selectedPrefix.id}&prefix_length=${prefixLength}`)
      const existing = candidate.subnet_id ? existingSubnets.find((subnet) => String(subnet.id) === String(candidate.subnet_id)) : undefined
      setSelectedSubnet(existing || { ...calculatedSubnet(candidate.cidr, prefixAddresses), id: candidate.subnet_id || undefined, prefix_id: selectedPrefix.id })
      notify(`${candidate.cidr} is the next available /${prefixLength} block.`, 'info')
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : 'No available subnet could be found.', 'error')
    } finally {
      setFindingNext(false)
    }
  }

  const allocateSelectedSubnet = async () => {
    if (!selectedPrefix || !selectedSubnet?.cidr) return
    setAllocatingNext(true)
    try {
      const allocated = await request<Subnet>('/subnets', { method: 'POST', body: { prefix_id: selectedPrefix.id, cidr: selectedSubnet.cidr, status: 'allocated' } })
      notify(`${allocated.cidr} was allocated.`)
      setSelectedSubnet(allocated)
      reloadSubnets()
      reloadPreview()
      reloadPrefixAddresses()
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : 'Unable to allocate the next subnet.', 'error')
    } finally {
      setAllocatingNext(false)
    }
  }

  const allocatePersistedSubnet = async () => {
    if (!selectedSubnet?.id) return
    setAllocatingNext(true)
    try {
      const allocated = await request<Subnet>(`/subnets/${selectedSubnet.id}`, { method: 'PATCH', body: { status: 'allocated' } })
      notify(`${allocated.cidr} was allocated.`)
      setSelectedSubnet(allocated)
      reloadSubnets()
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : 'Unable to allocate this subnet.', 'error')
    } finally {
      setAllocatingNext(false)
    }
  }

  const splitSelectedSubnet = async () => {
    if (!selectedSubnet?.id) return
    setSplitting(true)
    try {
      const children = await request<Subnet[]>(`/subnets/${selectedSubnet.id}/split`, { method: 'POST', body: { new_prefix_length: childPrefixLength } })
      notify(`${selectedSubnet.cidr} was split into ${children.length} child blocks.`)
      setPrefixLength(childPrefixLength)
      setSelectedSubnet(children[0] || null)
      reloadSubnets()
      reloadPreview()
      reloadPrefixAddresses()
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : 'Unable to split this subnet.', 'error')
    } finally {
      setSplitting(false)
    }
  }

  const choices = baseLength >= 32
    ? [32]
    : Array.from({ length: Math.max(0, maxPreviewLength - baseLength) }, (_, index) => baseLength + index + 1)
  const selectedLength = Number(selectedSubnet?.cidr.split('/')[1] || 32)
  const childChoices = Array.from({ length: Math.max(0, Math.min(32, selectedLength + 12) - selectedLength) }, (_, index) => selectedLength + index + 1)
  const previewAddresses = selectedSubnet && !selectedSubnet.id ? calculatedAddresses(selectedSubnet.cidr, prefixAddresses) : []
  return (
    <div className="page page--subnets">
      <PageHeader eyebrow="Visual planner" title="Subnet browser" description="Explore boundaries, utilization, and every address inside a child block." actions={<Button variant="secondary" onClick={() => { reloadSubnets(); reloadPreview(); reloadPrefixAddresses() }}><RefreshCw size={15} /> Refresh</Button>} />
      {subnetError && <ErrorState message={subnetError} onRetry={reloadSubnets} />}
      {prefixAddressError && <ErrorState message={prefixAddressError} onRetry={reloadPrefixAddresses} />}
      <Card className="subnet-workbench">
        <div className="subnet-controls">
          <div className="subnet-controls__group"><label htmlFor="prefix-select">Parent prefix</label><div className="select-wrap"><select id="prefix-select" value={selectedPrefixId} disabled={prefixesLoading} onChange={(event) => { setSelectedSubnet(null); setParams({ prefix: event.target.value }) }}>{prefixes.map((prefix) => <option key={prefix.id} value={prefix.id}>{prefix.cidr}{prefix.name ? ` · ${prefix.name}` : ''}</option>)}</select><ChevronsUpDown size={14} /></div></div>
          <div className="subnet-controls__group"><label htmlFor="size-select">View as</label><div className="select-wrap select-wrap--short"><select id="size-select" value={prefixLength} disabled={!selectedPrefix || baseLength >= 32} onChange={(event) => { setPrefixLength(Number(event.target.value)); setSelectedSubnet(null) }}>{choices.map((length) => <option key={length} value={length}>/{length} · {2 ** (32 - length)} IPs</option>)}</select><ChevronsUpDown size={14} /></div></div>
          <div className="subnet-controls__summary"><span>{blocks.length || (selectedPrefix ? 2 ** (prefixLength - baseLength) : 0)} blocks</span><Badge tone="neutral">{selectedPrefix?.cidr || 'No prefix'}</Badge></div>
          {!readOnly && <><Button size="small" variant="secondary" onClick={findNextSubnet} disabled={!selectedPrefix || baseLength >= 32 || findingNext}><Sparkles size={14} /> {findingNext ? 'Finding…' : 'Find next'}</Button><Button size="small" onClick={createSubnets} disabled={!selectedPrefix || baseLength >= 32 || creating}><Plus size={14} /> {creating ? 'Creating…' : 'Create blocks'}</Button></>}
        </div>
        <div className={`subnet-browser ${selectedSubnet ? 'subnet-browser--detail' : ''}`}>
          <div className="subnet-grid-panel">
            <div className="subnet-legend"><span><i className="swatch swatch--free" /> Mostly free</span><span><i className="swatch swatch--used" /> In use</span><span><i className="swatch swatch--full" /> Near capacity</span><span><i className="swatch swatch--uncreated" /> Preview</span></div>
            {previewLoading || prefixAddressesLoading || subnetsLoading ? <LoadingState label="Calculating address blocks…" /> : previewError ? <ErrorState message={previewError} onRetry={reloadPreview} /> : blocks.length ? (
              <div className="subnet-block-grid">
                {blocks.map((subnet, index) => {
                  const utilization = percentValue(subnet.utilization_percent ?? subnet.utilization ?? (subnet.total_addresses && subnet.used_addresses ? (subnet.used_addresses / subnet.total_addresses) * 100 : 0))
                  const created = Boolean(subnet.id)
                  return (
                    <button type="button" key={subnet.cidr || index} className={`subnet-block ${selectedSubnet?.cidr === subnet.cidr ? 'subnet-block--selected' : ''} ${!created ? 'subnet-block--preview' : ''}`} onClick={() => setSelectedSubnet(subnet)}>
                      <span className="subnet-block__top"><Network size={15} /><strong>{subnet.cidr}</strong>{created && <Check size={14} />}</span>
                      <span className="subnet-block__stats"><span>{formatNumber(subnet.free_addresses ?? networkSize(subnet.cidr))} free</span><span>{formatPercent(utilization)}</span></span>
                      <ProgressBar value={utilization} tone={utilization > 85 ? 'red' : utilization > 55 ? 'amber' : 'teal'} />
                    </button>
                  )
                })}
              </div>
            ) : <EmptyState icon={Grid3X3} title="No subnet blocks to show" description="Choose a prefix and subnet size to preview its child ranges." />}
          </div>
          {selectedSubnet && (
            <aside className="subnet-detail">
              <div className="subnet-detail__header"><button type="button" className="icon-button" onClick={() => setSelectedSubnet(null)} aria-label="Close subnet details"><ArrowLeft size={18} /></button><div><span>Selected subnet</span><h2>{selectedSubnet.cidr}</h2></div>{selectedSubnet.id ? <Badge tone="active">Active</Badge> : <Badge tone="neutral">Preview</Badge>}</div>
              <div className="subnet-detail__facts"><div><span>Usable range</span><strong className="mono">{selectedSubnet.first_usable_ip || '—'} – {selectedSubnet.last_usable_ip || '—'}</strong></div><div><span>Total addresses</span><strong>{formatNumber(selectedSubnet.total_addresses ?? networkSize(selectedSubnet.cidr))}</strong></div><div><span>Parent</span><strong>{selectedSubnet.parent_subnet_id ? `Subnet #${selectedSubnet.parent_subnet_id}` : 'Top-level prefix'}</strong></div></div>
              {!readOnly && selectedSubnet.id && selectedSubnet.status !== 'container' && selectedLength < 32 && <div className="subnet-split-action"><div><span>Subdivide this block</span><small>Persist child relationships and recalculate boundaries.</small></div><Select value={childPrefixLength} onChange={(event) => setChildPrefixLength(Number(event.target.value))}>{childChoices.map((length) => <option value={length} key={length}>/{length} · {2 ** (length - selectedLength)} blocks</option>)}</Select><Button size="small" variant="secondary" onClick={splitSelectedSubnet} disabled={splitting}>{splitting ? 'Splitting…' : 'Split block'}</Button></div>}
              {!selectedSubnet.id ? (
                <div className="address-mini-list">
                  <div className="address-mini-list__heading"><span>Calculated addresses</span>{!readOnly && <Button size="small" onClick={allocateSelectedSubnet} disabled={allocatingNext}><Plus size={14} /> {allocatingNext ? 'Allocating…' : 'Allocate this block'}</Button>}</div>
                  <div className="address-mini-list__search"><Search size={14} /> Preview only · create the block to manage its addresses</div>
                  {previewAddresses.map((address) => <div key={address.id} className="address-mini-row"><span className={`address-status-dot address-status-dot--${address.status}`} /><span className="mono">{address.address}</span><StatusBadge status={address.status} /></div>)}
                  {(selectedSubnet.total_addresses || 0) > previewAddresses.length && <p className="muted-copy">Showing the first {previewAddresses.length} calculated addresses.</p>}
                </div>
              ) : addressError ? <ErrorState message={addressError} /> : addressesLoading ? <LoadingState label="Loading addresses…" /> : (
                <div className="address-mini-list">
                  <div className="address-mini-list__heading"><span>Addresses</span><div>{!readOnly && selectedSubnet.status === 'free' && <Button size="small" onClick={allocatePersistedSubnet} disabled={allocatingNext}>{allocatingNext ? 'Allocating…' : 'Allocate block'}</Button>}<Link to={`/ip-addresses?subnet=${selectedSubnet.id}`} className="text-link">Open full table</Link></div></div>
                  <div className="address-mini-list__search"><Search size={14} /> Click an IP to manage it</div>
                  {addresses.slice(0, 64).map((address) => <Link key={address.id} to={`/ip-addresses?search=${encodeURIComponent(address.address || address.ip_address || '')}`} className="address-mini-row"><span className={`address-status-dot address-status-dot--${address.status}`} /><span className="mono">{address.address || address.ip_address}</span><StatusBadge status={address.status} /></Link>)}
                  {!addresses.length && <EmptyState title="No addresses returned" description="The subnet exists, but it has no address records yet." />}
                </div>
              )}
            </aside>
          )}
        </div>
      </Card>
    </div>
  )
}
