import {
  ArrowDownUp,
  CheckCircle2,
  Clock3,
  Download,
  Globe2,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Shield,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Badge, Button, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Pagination, Select, SkeletonRows, StatusBadge, TableContainer, Textarea } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useApiData } from '../hooks/useApiData'
import { normalizeIp, queryString, request, unwrapList } from '../lib/api'
import { formatDate, titleCase } from '../lib/format'
import type { Customer, Device, Id, IpAddress, Prefix, Router, Subnet } from '../types'

type AddressAction = 'details' | 'assign' | 'reserve' | 'edit' | 'release'
type AssignmentForm = {
  status: string
  hostname: string
  device_id: string
  customer_id: string
  purpose: string
  location: string
  router_id: string
  interface: string
  vlan: string
  mac_address: string
  reverse_dns: string
  notes: string
}

const EMPTY_FORM: AssignmentForm = {
  status: 'assigned', hostname: '', device_id: '', customer_id: '', purpose: '', location: '', router_id: '', interface: '', vlan: '', mac_address: '', reverse_dns: '', notes: '',
}

function valueId(value: Id | null | undefined) {
  return value === null || value === undefined ? '' : String(value)
}

function initialForm(address: IpAddress): AssignmentForm {
  return {
    ...EMPTY_FORM,
    status: address.status === 'free' ? 'assigned' : address.status,
    hostname: address.hostname || '',
    device_id: valueId(address.device_id || address.device?.id),
    customer_id: valueId(address.customer_id || address.customer?.id),
    purpose: address.purpose || '',
    location: address.location || '',
    router_id: valueId(address.router_id || address.router?.id),
    interface: address.interface || '',
    vlan: valueId(address.vlan),
    mac_address: address.mac_address || '',
    reverse_dns: address.reverse_dns || '',
    notes: address.notes || '',
  }
}

function cleanPayload(form: AssignmentForm) {
  return Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim() || null]))
}

function AddressDialog({ address, initialAction, devices, customers, routers, readOnly, onClose, onChanged }: { address: IpAddress; initialAction: AddressAction; devices: Device[]; customers: Customer[]; routers: Router[]; readOnly: boolean; onClose: () => void; onChanged: () => void }) {
  const [action, setAction] = useState<AddressAction>(initialAction)
  const [form, setForm] = useState<AssignmentForm>(() => initialForm(address))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const { notify } = useToast()
  const addressText = address.address || address.ip_address || ''
  const deviceName = address.device_name || address.device?.name || devices.find((item) => String(item.id) === String(address.device_id))?.name
  const customerName = address.customer_name || address.customer?.name || customers.find((item) => String(item.id) === String(address.customer_id))?.name
  const routerName = address.router_name || address.router?.name || routers.find((item) => String(item.id) === String(address.router_id))?.name
  const historyPath = address.id ? `/ip-addresses/${address.id}/history?limit=500` : null
  const { data: historyData, loading: historyLoading } = useApiData<unknown>(historyPath, [])
  const history = unwrapList<{ id: Id; action?: string; status?: string; assigned_at?: string; released_at?: string; created_at?: string; actor_id?: Id | null; purpose?: string; snapshot?: Record<string, unknown> }>(historyData)
  const update = (field: keyof AssignmentForm, value: string) => setForm((current) => ({ ...current, [field]: value }))

  const save = async (event?: FormEvent) => {
    event?.preventDefault()
    if (!address.id) {
      setError('This address does not have a server record yet.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = cleanPayload(form)
      if (action === 'release') {
        await request(`/ip-addresses/${address.id}/release`, { method: 'POST' })
        notify(`${addressText} is now free.`)
      } else if (action === 'reserve') {
        delete payload.status
        if (!payload.purpose) payload.purpose = 'Reserved'
        await request(`/ip-addresses/${address.id}/reserve`, { method: 'POST', body: payload })
        notify(`${addressText} was reserved.`)
      } else if (action === 'edit') {
        await request(`/ip-addresses/${address.id}`, { method: 'PATCH', body: payload })
        notify(`${addressText} was updated.`)
      } else {
        await request(`/ip-addresses/${address.id}/assign`, { method: 'POST', body: payload })
        notify(`${addressText} was assigned.`)
      }
      onChanged()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update this address.')
    } finally {
      setSaving(false)
    }
  }

  const isForm = action === 'assign' || action === 'reserve' || action === 'edit'
  const mutableStatus = !address.reserved_by_subnet && ['assigned', 'reserved', 'gateway', 'blackholed'].includes(address.status)
  const title = action === 'details' ? addressText : `${titleCase(action)} ${addressText}`
  return (
    <Modal title={title} description={action === 'details' ? 'Assignment details and retained allocation history.' : action === 'release' ? 'Release the current assignment while preserving its audit history.' : 'Update the operational details for this address.'} onClose={onClose} size="large">
      {error && <div className="form-alert" role="alert">{error}</div>}
      {action === 'details' ? (
        <div className="address-details">
          <div className="address-detail-hero"><div><span>IP address</span><strong className="mono">{addressText}</strong></div><StatusBadge status={address.status} /></div>
          {address.reserved_by_subnet && <div className="form-alert">This address is held by its reserved subnet. Change the subnet status before editing or releasing the address.</div>}
          <div className="detail-grid">
            <div><span>Hostname</span><strong>{address.hostname || '—'}</strong></div><div><span>Purpose</span><strong>{address.purpose || '—'}</strong></div>
            <div><span>Device</span><strong>{deviceName || '—'}</strong></div><div><span>Customer</span><strong>{customerName || '—'}</strong></div>
            <div><span>Router / interface</span><strong>{routerName || '—'}{address.interface ? ` · ${address.interface}` : ''}</strong></div><div><span>VLAN</span><strong>{address.vlan || '—'}</strong></div>
            <div><span>MAC address</span><strong className="mono">{address.mac_address || '—'}</strong></div><div><span>Reverse DNS</span><strong>{address.reverse_dns || '—'}</strong></div>
            <div><span>Location</span><strong>{address.location || '—'}</strong></div><div><span>Last modified</span><strong>{formatDate(address.updated_at)}</strong></div>
          </div>
          {address.notes && <div className="detail-notes"><span>Notes</span><p>{address.notes}</p></div>}
          <div className="history-section">
            <div className="history-section__heading"><div><Clock3 size={17} /><strong>Allocation history</strong></div><Badge tone="neutral">Latest {history.length} events</Badge></div>
            {historyLoading ? <div className="loading-inline">Loading history…</div> : history.length ? (
              <><div className="timeline">{history.map((entry) => <div className="timeline__item" key={entry.id}><i /><div><strong>{titleCase(entry.action || entry.status || 'allocation updated')}</strong><span>{entry.purpose || String(entry.snapshot?.purpose || 'Address record changed')} · {entry.actor_id ? `User #${entry.actor_id}` : 'System'}</span></div><time>{formatDate(entry.created_at || entry.assigned_at || entry.released_at)}</time></div>)}</div>{history.length === 500 && <p className="muted-copy">Showing the latest 500 retained events.</p>}</>
            ) : <p className="muted-copy">No prior allocation events were returned.</p>}
          </div>
          <div className="modal__actions modal__actions--spread">
            <div>{!readOnly && mutableStatus && <Button variant="danger" onClick={() => setAction('release')}><Trash2 size={15} /> Release</Button>}</div>
            <div><Button variant="ghost" onClick={onClose}>Close</Button>{!readOnly && address.status === 'free' ? <><Button variant="secondary" onClick={() => setAction('reserve')}><Shield size={15} /> Reserve</Button><Button onClick={() => setAction('assign')}><Plus size={15} /> Assign</Button></> : !readOnly && mutableStatus ? <Button onClick={() => setAction('edit')}><Pencil size={15} /> Edit assignment</Button> : null}</div>
          </div>
        </div>
      ) : action === 'release' ? (
        <form onSubmit={save} className="form-stack">
          <div className="danger-callout"><XCircle size={20} /><div><strong>Release {addressText}?</strong><p>The address will return to the free pool. Its current and previous allocation records remain in the audit history.</p></div></div>
          <div className="modal__actions"><Button type="button" variant="ghost" onClick={() => setAction('details')}>Cancel</Button><Button type="submit" variant="danger" disabled={saving}>{saving ? 'Releasing…' : 'Release address'}</Button></div>
        </form>
      ) : isForm ? (
        <form onSubmit={save} className="assignment-form">
          <div className="assignment-form__summary"><Globe2 size={18} /><div><span>Selected address</span><strong className="mono">{addressText}</strong></div><StatusBadge status={address.status} /></div>
          <div className="form-grid">
            {action !== 'reserve' && <Field label="Status" required><Select value={form.status} onChange={(event) => update('status', event.target.value)}>{action === 'edit' && <option value="reserved">Reserved</option>}<option value="assigned">Assigned</option><option value="gateway">Gateway</option><option value="blackholed">Blackholed</option></Select></Field>}
            <Field label="Hostname"><Input autoFocus value={form.hostname} onChange={(event) => update('hostname', event.target.value)} placeholder="edge-01.example.net" /></Field>
            <Field label="Purpose" required={action === 'assign'}><Input value={form.purpose} onChange={(event) => update('purpose', event.target.value)} placeholder={action === 'reserve' ? 'Reason for reservation' : 'Web service, hypervisor…'} required={action === 'assign'} /></Field>
            <Field label="Device"><Select value={form.device_id} onChange={(event) => update('device_id', event.target.value)}><option value="">No device</option>{devices.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
            <Field label="Customer"><Select value={form.customer_id} onChange={(event) => update('customer_id', event.target.value)}><option value="">No customer</option>{customers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
            <Field label="Router"><Select value={form.router_id} onChange={(event) => update('router_id', event.target.value)}><option value="">No router</option>{routers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
            <Field label="Interface"><Input value={form.interface} onChange={(event) => update('interface', event.target.value)} placeholder="ether1, vlan98…" /></Field>
            <Field label="VLAN"><Input inputMode="numeric" value={form.vlan} onChange={(event) => update('vlan', event.target.value)} placeholder="98" /></Field>
            <Field label="MAC address"><Input value={form.mac_address} onChange={(event) => update('mac_address', event.target.value)} placeholder="00:11:22:33:44:55" /></Field>
            <Field label="Location"><Input value={form.location} onChange={(event) => update('location', event.target.value)} placeholder="Rack, site, or room" /></Field>
            <Field label="Reverse DNS"><Input value={form.reverse_dns} onChange={(event) => update('reverse_dns', event.target.value)} placeholder="host.example.net" /></Field>
          </div>
          <Field label="Notes"><Textarea rows={3} value={form.notes} onChange={(event) => update('notes', event.target.value)} placeholder="Operational context, ticket number, or handoff notes…" /></Field>
          <div className="modal__actions"><Button type="button" variant="ghost" onClick={() => setAction('details')}>Cancel</Button><Button type="submit" disabled={saving}>{action === 'reserve' ? <Shield size={15} /> : action === 'edit' ? <CheckCircle2 size={15} /> : <Plus size={15} />}{saving ? 'Saving…' : action === 'reserve' ? 'Reserve address' : action === 'edit' ? 'Save changes' : 'Assign address'}</Button></div>
        </form>
      ) : null}
    </Modal>
  )
}

function CsvExport({ rows }: { rows: IpAddress[] }) {
  const download = () => {
    const header = ['IP address', 'Status', 'Hostname', 'Device', 'Customer', 'Purpose', 'Router', 'Interface', 'VLAN', 'MAC address', 'Reverse DNS', 'Updated']
    const values = rows.map((item) => [item.address || item.ip_address, item.status, item.hostname, item.device_name || item.device?.name, item.customer_name || item.customer?.name, item.purpose, item.router_name || item.router?.name, item.interface, item.vlan, item.mac_address, item.reverse_dns, item.updated_at])
    const csvCell = (value: unknown) => {
      const text = String(value ?? '')
      const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
      return `"${safe.replaceAll('"', '""')}"`
    }
    const csv = [header, ...values].map((row) => row.map(csvCell).join(',')).join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'merbag-ip-addresses.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }
  return <Button variant="secondary" onClick={download} disabled={!rows.length}><Download size={15} /> Export view</Button>
}

export function IpAddressesPage() {
  const [params, setParams] = useSearchParams()
  const initialSearch = params.get('search') || ''
  const [searchDraft, setSearchDraft] = useState(initialSearch)
  const [selected, setSelected] = useState<{ address: IpAddress; action: AddressAction } | null>(null)
  const [findingNext, setFindingNext] = useState(false)
  const { notify } = useToast()
  const { user } = useAuth()
  const readOnly = user?.role === 'read_only'
  const page = Math.max(1, Number(params.get('page') || 1))
  const pageSize = Math.min(100, Math.max(10, Number(params.get('page_size') || 25)))
  const status = params.get('status') || ''
  const subnetId = params.get('subnet') || ''

  useEffect(() => {
    setSearchDraft(initialSearch)
  }, [initialSearch])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const current = params.get('search') || ''
      if (current === searchDraft.trim()) return
      const next = new URLSearchParams(params)
      searchDraft.trim() ? next.set('search', searchDraft.trim()) : next.delete('search')
      next.delete('page')
      setParams(next, { replace: true })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchDraft, params, setParams])

  const { data: subnetData } = useApiData<unknown>('/subnets?limit=2000', [])
  const { data: prefixData } = useApiData<unknown>('/prefixes', [])
  const subnets = unwrapList<Subnet>(subnetData)
  const prefixes = unwrapList<Prefix>(prefixData)
  const subnetPrefixId = subnetId ? String(subnets.find((item) => String(item.id) === subnetId)?.prefix_id || '') : ''
  const filterPrefixId = params.get('prefix') || ''
  const nextAvailablePrefixId = subnetPrefixId || filterPrefixId || (prefixes[0] ? String(prefixes[0].id) : '')
  const listPath = `/ip-addresses${queryString({ q: initialSearch, status, prefix_id: filterPrefixId, subnet_id: subnetId, skip: (page - 1) * pageSize, limit: pageSize + 1 })}`
  const { data, loading, error, reload } = useApiData<unknown>(listPath, [])
  const { data: deviceData } = useApiData<unknown>('/devices?limit=500', [])
  const { data: customerData } = useApiData<unknown>('/customers?limit=500', [])
  const { data: routerData } = useApiData<unknown>('/routers?limit=500', [])
  const devices = unwrapList<Device>(deviceData)
  const customers = unwrapList<Customer>(customerData)
  const routers = unwrapList<Router>(routerData)
  const batch = unwrapList<IpAddress>(data)
  const hasNext = batch.length > pageSize
  const addresses = batch.slice(0, pageSize).map((rawAddress) => {
    const address = normalizeIp(rawAddress)
    return {
      ...address,
      device_name: address.device_name || address.device?.name || devices.find((item) => String(item.id) === String(address.device_id))?.name,
      customer_name: address.customer_name || address.customer?.name || customers.find((item) => String(item.id) === String(address.customer_id))?.name,
      router_name: address.router_name || address.router?.name || routers.find((item) => String(item.id) === String(address.router_id))?.name,
    }
  })
  const visibleTotal = (page - 1) * pageSize + addresses.length

  const updateParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    value ? next.set(key, value) : next.delete(key)
    if (key !== 'page') next.delete('page')
    setParams(next)
  }

  const updatePrefix = (value: string) => {
    const next = new URLSearchParams(params)
    value ? next.set('prefix', value) : next.delete('prefix')
    next.delete('subnet')
    next.delete('page')
    setParams(next)
  }

  const findNext = async (toolSubnetId?: string) => {
    setFindingNext(true)
    try {
      const chosenSubnet = toolSubnetId || subnetId
      const chosenPrefix = chosenSubnet ? String(subnets.find((item) => String(item.id) === chosenSubnet)?.prefix_id || nextAvailablePrefixId) : nextAvailablePrefixId
      if (!chosenPrefix) throw new Error('Add or select a prefix before finding an available address.')
      const payload = await request<unknown>(`/ip-addresses/next-available${queryString({ prefix_id: chosenPrefix, subnet_id: chosenSubnet })}`)
      const record = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
      const raw = (record.ip_address && typeof record.ip_address === 'object' ? record.ip_address : record.address && typeof record.address === 'object' ? record.address : payload) as IpAddress
      const nextAddress = normalizeIp(raw)
      if (!nextAddress.id && typeof record.id !== 'undefined') nextAddress.id = record.id as Id
      if (!nextAddress.address && typeof record.address === 'string') nextAddress.address = record.address
      if (!nextAddress.address) throw new Error('No available address was returned.')
      setSelected({ address: { ...nextAddress, status: nextAddress.status || 'free' }, action: 'assign' })
      return nextAddress
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'No available address could be found.'
      notify(message, 'error')
      throw reason
    } finally {
      setFindingNext(false)
    }
  }

  useEffect(() => {
    const context = document.modelContext
    if (!context?.registerTool) return
    const lifecycle = new AbortController()
    try {
      void Promise.resolve(context.registerTool({
        name: 'find_next_available_ip',
        title: 'Find next available IP',
        description: 'Find the next free IP address, optionally within a subnet, and open the visible assignment workflow.',
        inputSchema: { type: 'object', properties: { subnetId: { type: 'string', description: 'Optional subnet record ID.' } }, additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: false },
        execute: async (input: unknown) => {
          const candidate = input && typeof input === 'object' ? (input as { subnetId?: unknown }).subnetId : undefined
          const found = await findNext(typeof candidate === 'string' ? candidate : undefined)
          return { id: found.id, address: found.address, status: found.status || 'free', workflow: 'assignment_opened' }
        },
      }, { signal: lifecycle.signal })).catch(() => undefined)
    } catch {
      // WebMCP is optional and may be present only as a partial browser implementation.
    }
    return () => lifecycle.abort()
  }, [subnetId, nextAvailablePrefixId])

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    addresses.forEach((address) => { counts[address.status] = (counts[address.status] || 0) + 1 })
    return counts
  }, [addresses])

  return (
    <div className="page">
      <PageHeader eyebrow="Allocation workspace" title="IP addresses" description="Scan availability quickly, then assign, reserve, edit, or release an address." actions={<><CsvExport rows={addresses} />{!readOnly && <Button onClick={() => void findNext().catch(() => undefined)} disabled={findingNext}><Sparkles size={16} /> {findingNext ? 'Finding…' : 'Next available'}</Button>}</>} />
      {error && <ErrorState message={error} onRetry={reload} />}
      <section className="ip-table-card">
        <div className="ip-toolbar">
          <div className="search-input search-input--wide"><Search size={16} /><Input value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="Search IP, hostname, MAC, customer…" /></div>
          <Select value={filterPrefixId} onChange={(event) => updatePrefix(event.target.value)} aria-label="Filter by prefix"><option value="">All prefixes</option>{prefixes.map((prefix) => <option key={prefix.id} value={prefix.id}>{prefix.cidr}</option>)}</Select>
          <Select value={subnetId} onChange={(event) => updateParam('subnet', event.target.value)} aria-label="Filter by subnet"><option value="">All subnets</option>{subnets.filter((subnet) => !filterPrefixId || String(subnet.prefix_id) === filterPrefixId).map((subnet) => <option key={subnet.id} value={subnet.id}>{subnet.cidr}{subnet.name ? ` · ${subnet.name}` : ''}</option>)}</Select>
          <Select value={String(pageSize)} onChange={(event) => updateParam('page_size', event.target.value)} aria-label="Rows per page"><option value="25">25 rows</option><option value="50">50 rows</option><option value="100">100 rows</option></Select>
        </div>
        <div className="status-tabs" role="tablist" aria-label="Address status filter">
          {['', 'free', 'assigned', 'reserved', 'gateway', 'blackholed'].map((item) => <button type="button" role="tab" aria-selected={status === item} className={status === item ? 'status-tab status-tab--active' : 'status-tab'} key={item || 'all'} onClick={() => updateParam('status', item)}>{item ? titleCase(item) : 'All'}{item && statusCounts[item] !== undefined && <span>{statusCounts[item]}</span>}</button>)}
        </div>
        <TableContainer>
          <thead><tr><th><span className="sortable-heading">IP address <ArrowDownUp size={12} /></span></th><th>Status</th><th>Hostname / device</th><th>Customer / purpose</th><th>Network</th><th>Last modified</th><th><span className="sr-only">Actions</span></th></tr></thead>
          {loading ? <SkeletonRows rows={10} columns={7} /> : (
            <tbody>
              {addresses.map((address) => (
                <tr key={address.id} className="clickable-row" onClick={() => setSelected({ address, action: 'details' })}>
                  <td><button type="button" className="mono-link row-primary-action" onClick={(event) => { event.stopPropagation(); setSelected({ address, action: 'details' }) }}>{address.address}</button></td>
                  <td><StatusBadge status={address.status} /></td>
                  <td><strong className="table-primary">{address.hostname || '—'}</strong><small className="table-secondary">{address.device_name || address.device?.name || devices.find((item) => String(item.id) === String(address.device_id))?.name}</small></td>
                  <td><strong className="table-primary">{address.customer_name || address.customer?.name || customers.find((item) => String(item.id) === String(address.customer_id))?.name || '—'}</strong><small className="table-secondary">{address.purpose}</small></td>
                  <td><span className="table-primary mono text-small">{address.subnet?.cidr || subnets.find((item) => String(item.id) === String(address.subnet_id))?.cidr || '—'}</span><small className="table-secondary">{address.interface ? `${address.router_name || address.router?.name || routers.find((item) => String(item.id) === String(address.router_id))?.name || ''} · ${address.interface}` : address.location}</small></td>
                  <td>{formatDate(address.updated_at, false)}</td>
                  <td><button type="button" className="icon-button" aria-label={`Actions for ${address.address}`} onClick={(event) => { event.stopPropagation(); setSelected({ address, action: 'details' }) }}><MoreHorizontal size={18} /></button></td>
                </tr>
              ))}
            </tbody>
          )}
        </TableContainer>
        {!loading && addresses.length === 0 && <EmptyState icon={Globe2} title="No addresses found" description={initialSearch || status || subnetId ? 'Adjust your filters or clear the search to see more addresses.' : 'Addresses will appear once a prefix or subnet has been created.'} action={(initialSearch || status || subnetId) && <Button variant="secondary" onClick={() => { setSearchDraft(''); setParams({}) }}>Clear filters</Button>} />}
        <Pagination page={page} pages={hasNext ? page + 1 : page} total={visibleTotal} pageSize={pageSize} hasNext={hasNext} totalExact={false} onPageChange={(nextPage) => updateParam('page', String(nextPage))} />
      </section>
      {selected && <AddressDialog address={selected.address} initialAction={readOnly ? 'details' : selected.action} devices={devices} customers={customers} routers={routers} readOnly={readOnly} onClose={() => setSelected(null)} onChanged={reload} />}
    </div>
  )
}
