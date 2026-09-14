import { Boxes, Network, Plus, Scissors, Search } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, LoadingState, Modal, PageHeader, ProgressBar, SkeletonRows, TableContainer, Textarea } from '../components/ui'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { useApiData } from '../hooks/useApiData'
import { request, unwrapList } from '../lib/api'
import { formatNumber, formatPercent, percentValue } from '../lib/format'
import type { Prefix, Subnet } from '../types'

function AddPrefixDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [cidr, setCidr] = useState('')
  const [location, setLocation] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const { notify } = useToast()
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!cidr.trim() || !/^\d{1,3}(\.\d{1,3}){3}\/\d{1,2}$/.test(cidr.trim())) {
      setError('Enter a valid IPv4 CIDR, for example 203.0.113.0/24.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await request('/prefixes', { method: 'POST', body: { cidr: cidr.trim(), location: location.trim() || undefined, description: description.trim() || undefined } })
      notify(`${cidr.trim()} was added.`)
      onCreated()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to add prefix.')
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title="Add IPv4 prefix" description="Network boundaries and usable address ranges are calculated automatically." onClose={onClose}>
      <form onSubmit={submit} className="form-stack">
        {error && <div className="form-alert" role="alert">{error}</div>}
        <Field label="Prefix (CIDR)" required hint="Use canonical IPv4 CIDR notation."><Input autoFocus value={cidr} onChange={(event) => setCidr(event.target.value)} placeholder="203.0.113.0/24" /></Field>
        <Field label="Location"><Input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Datacenter, POP, or region" /></Field>
        <Field label="Description"><Textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="How this address space is used…" /></Field>
        <div className="modal__actions"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Adding…' : 'Add prefix'}</Button></div>
      </form>
    </Modal>
  )
}

function SplitPrefixDialog({ prefix, onClose, onCreated }: { prefix: Prefix; onClose: () => void; onCreated: () => void }) {
  const baseLength = Number(prefix.cidr.split('/')[1] || 24)
  // The API supports larger programmatic splits; the modal deliberately keeps
  // its rendered preview to at most 1,024 child blocks.
  const maxPreviewLength = Math.min(32, baseLength + 10)
  const splittable = baseLength < 32
  const choices = splittable
    ? Array.from({ length: Math.max(0, maxPreviewLength - baseLength) }, (_, index) => baseLength + index + 1)
    : [32]
  const [prefixLength, setPrefixLength] = useState(
    splittable ? Math.min(maxPreviewLength, Math.max(baseLength + 1, 29)) : 32,
  )
  const path = splittable ? `/prefixes/${prefix.id}/split-preview?new_prefix_length=${prefixLength}` : null
  const { data, loading, error } = useApiData<unknown>(path, [])
  const [saving, setSaving] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const { notify } = useToast()
  const preview = unwrapList<string>(data).map((cidr) => ({ cidr } as Subnet))
  const create = async () => {
    setSaving(true)
    setSubmitError('')
    try {
      await request(`/prefixes/${prefix.id}/split`, { method: 'POST', body: { new_prefix_length: prefixLength } })
      notify(`${prefix.cidr} was split into /${prefixLength} subnets.`)
      onCreated()
      onClose()
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : 'Unable to create subnets.')
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title={`Split ${prefix.cidr}`} description="Preview the child ranges before creating them. Existing allocations are protected by the server." onClose={onClose} size="large">
      <div className="form-stack">
        {submitError && <div className="form-alert" role="alert">{submitError}</div>}
        <div className="split-controls">
          <Field label="Child subnet size"><select className="select" value={prefixLength} disabled={!splittable} onChange={(event) => setPrefixLength(Number(event.target.value))}>{choices.map((length) => <option key={length} value={length}>/{length} · {2 ** (32 - length)} addresses</option>)}</select></Field>
          <div className="split-result"><span>Result</span><strong>{preview.length || 2 ** (prefixLength - baseLength)} blocks</strong></div>
        </div>
        {loading ? <LoadingState label="Calculating subnet boundaries…" /> : error ? <div className="form-alert">{error}</div> : (
          <div className="subnet-preview-list">
            {preview.slice(0, 64).map((subnet, index) => <div key={subnet.id || subnet.cidr || index}><Network size={15} /><span>{subnet.cidr}</span><small>{subnet.first_usable_ip && subnet.last_usable_ip ? `${subnet.first_usable_ip} – ${subnet.last_usable_ip}` : 'Calculated block'}</small></div>)}
          </div>
        )}
        <div className="modal__actions"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={create} disabled={!splittable || saving || Boolean(error)}><Scissors size={15} /> {saving ? 'Creating…' : splittable ? `Create /${prefixLength} subnets` : 'Cannot split /32'}</Button></div>
      </div>
    </Modal>
  )
}

export function PrefixesPage() {
  const { data, loading, error, reload } = useApiData<unknown>('/prefixes', [])
  const [addOpen, setAddOpen] = useState(false)
  const [splitPrefix, setSplitPrefix] = useState<Prefix | null>(null)
  const [params, setParams] = useSearchParams()
  const { user } = useAuth()
  const readOnly = user?.role === 'read_only'
  const search = params.get('search') || ''
  const prefixes = unwrapList<Prefix>(data)
  const filtered = useMemo(() => prefixes.filter((prefix) => `${prefix.cidr} ${prefix.name || ''} ${prefix.description || ''}`.toLowerCase().includes(search.toLowerCase())), [prefixes, search])
  return (
    <div className="page">
      <PageHeader eyebrow="Address space" title="Prefixes" description="Define top-level IPv4 ranges and divide them into operational subnets." actions={!readOnly && <Button onClick={() => setAddOpen(true)}><Plus size={16} /> Add prefix</Button>} />
      {error && <ErrorState message={error} onRetry={reload} />}
      <Card>
        <div className="table-toolbar"><div className="search-input"><Search size={16} /><Input value={search} onChange={(event) => setParams(event.target.value ? { search: event.target.value } : {})} placeholder="Search prefixes…" /></div><Badge tone="neutral">{prefixes.length} prefixes</Badge></div>
        <TableContainer>
          <thead><tr><th>Prefix</th><th>Address range</th><th>Utilization</th><th>Total</th><th>Free</th><th><span className="sr-only">Actions</span></th></tr></thead>
          {loading ? <SkeletonRows rows={4} columns={6} /> : (
            <tbody>
              {filtered.map((prefix) => {
                const utilization = percentValue(prefix.utilization_percent ?? prefix.utilization)
                return (
                  <tr key={prefix.id}>
                    <td><div className="prefix-cell"><span className="object-icon"><Boxes size={17} /></span><span><Link to={`/subnets?prefix=${prefix.id}`} className="mono-link">{prefix.cidr}</Link><small>{prefix.location || prefix.description || 'Managed IPv4 prefix'}</small></span></div></td>
                    <td><span className="mono text-small">{prefix.first_usable_ip || prefix.network_address || '—'}</span><span className="range-separator">→</span><span className="mono text-small">{prefix.last_usable_ip || prefix.broadcast_address || '—'}</span></td>
                    <td><div className="table-progress"><ProgressBar value={utilization} /><strong>{formatPercent(utilization)}</strong></div></td>
                    <td>{formatNumber(prefix.total_addresses)}</td><td>{formatNumber(prefix.free_addresses)}</td>
                    <td>{!readOnly && <Button size="small" variant="secondary" onClick={() => setSplitPrefix(prefix)}><Scissors size={14} /> Split</Button>}</td>
                  </tr>
                )
              })}
            </tbody>
          )}
        </TableContainer>
        {!loading && filtered.length === 0 && <EmptyState icon={Boxes} title={search ? 'No matching prefixes' : 'No prefixes yet'} description={search ? 'Try a different search term.' : 'Add the first IPv4 range you want merbag IPAM to manage.'} action={!search && !readOnly && <Button onClick={() => setAddOpen(true)}><Plus size={15} /> Add prefix</Button>} />}
      </Card>
      {addOpen && <AddPrefixDialog onClose={() => setAddOpen(false)} onCreated={reload} />}
      {splitPrefix && <SplitPrefixDialog prefix={splitPrefix} onClose={() => setSplitPrefix(null)} onCreated={reload} />}
    </div>
  )
}
