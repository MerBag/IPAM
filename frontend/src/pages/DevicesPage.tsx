import { Server } from 'lucide-react'
import { ResourcePage, type ResourceColumn, type ResourceField } from '../components/ResourcePage'
import { Badge } from '../components/ui'
import { formatDate, formatNumber } from '../lib/format'
import type { Device } from '../types'

const fields: ResourceField<Device>[] = [
  { key: 'name', label: 'Name', placeholder: 'edge-hv-01', required: true },
  { key: 'type', label: 'Device type', type: 'select', required: true, defaultValue: 'other', options: [{ label: 'MikroTik', value: 'mikrotik' }, { label: 'Linux Server', value: 'linux_server' }, { label: 'Windows Server', value: 'windows_server' }, { label: 'Switch', value: 'switch' }, { label: 'VM Host', value: 'vm_host' }, { label: 'VM', value: 'vm' }, { label: 'Customer Router', value: 'customer_router' }, { label: 'Other', value: 'other' }] },
  { key: 'management_ip', label: 'Management IP', placeholder: '10.0.0.10' },
  { key: 'mac_address', label: 'MAC address', placeholder: '00:11:22:33:44:55' },
  { key: 'location', label: 'Location', placeholder: 'DC1 · Rack B04' },
  { key: 'description', label: 'Description', type: 'textarea', placeholder: 'Role, owner, or operational context…', fullWidth: true },
]

const columns: ResourceColumn<Device>[] = [
  { key: 'name', label: 'Device', render: (item) => <div className="entity-cell"><span className="object-icon"><Server size={16} /></span><span><strong>{item.name}</strong><small>{item.description}</small></span></div> },
  { key: 'type', label: 'Type', render: (item) => <Badge tone="neutral">{item.type || 'Other'}</Badge> },
  { key: 'management', label: 'Management', render: (item) => <><span className="mono text-small">{item.management_ip || '—'}</span><small className="table-secondary mono">{item.mac_address}</small></> },
  { key: 'location', label: 'Location', render: (item) => item.location || '—' },
  { key: 'addresses', label: 'IPs', render: (item) => formatNumber(item.ip_count ?? 0) },
  { key: 'updated', label: 'Updated', render: (item) => formatDate(item.updated_at, false) },
]

export function DevicesPage() {
  return <ResourcePage<Device> endpoint="/devices" noun="Device" nounPlural="Devices" eyebrow="Infrastructure inventory" description="Track servers, routers, switches, hosts, and virtual machines tied to your addresses." icon={Server} fields={fields} columns={columns} />
}
