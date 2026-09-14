import { Router } from 'lucide-react'
import { ResourcePage, type ResourceColumn, type ResourceField } from '../components/ResourcePage'
import { Badge, StatusBadge } from '../components/ui'
import { formatDate, formatNumber } from '../lib/format'
import type { Router as RouterRecord } from '../types'

const fields: ResourceField<RouterRecord>[] = [
  { key: 'name', label: 'Router name', placeholder: 'core-rtr-01', required: true },
  { key: 'management_ip', label: 'Management IP', placeholder: '10.0.0.1', required: true },
  { key: 'api_port', label: 'RouterOS API port', placeholder: '8728', defaultValue: '8728' },
  { key: 'username', label: 'API username', placeholder: 'Optional; no password is stored here' },
  { key: 'location', label: 'Location', placeholder: 'Core POP' },
  { key: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Role, routing domain, or connection notes…', fullWidth: true },
]

const columns: ResourceColumn<RouterRecord>[] = [
  { key: 'name', label: 'Router', render: (item) => <div className="entity-cell"><span className="object-icon"><Router size={16} /></span><span><strong>{item.name}</strong><small>{item.username ? `${item.username} · API ${item.api_port || 8728}` : `API ${item.api_port || 8728}`}</small></span></div> },
  { key: 'management_ip', label: 'Management IP', render: (item) => <span className="mono text-small">{item.management_ip || '—'}</span> },
  { key: 'location', label: 'Location', render: (item) => item.location || '—' },
  { key: 'status', label: 'Integration', render: (item) => item.enabled ? <StatusBadge status="active" /> : <Badge tone="neutral">Disabled</Badge> },
  { key: 'addresses', label: 'IPs', render: (item) => formatNumber(item.ip_count ?? 0) },
  { key: 'updated', label: 'Updated', render: (item) => formatDate(item.updated_at, false) },
]

export function RoutersPage() {
  return <ResourcePage<RouterRecord> endpoint="/routers" noun="Router" nounPlural="Routers" eyebrow="Routing inventory" description="Document router ownership and interfaces now; add RouterOS discovery safely later." icon={Router} fields={fields} columns={columns} />
}
