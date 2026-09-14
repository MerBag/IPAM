import { Mail, UsersRound } from 'lucide-react'
import { ResourcePage, type ResourceColumn, type ResourceField } from '../components/ResourcePage'
import { Badge } from '../components/ui'
import { formatDate, formatNumber } from '../lib/format'
import type { Customer } from '../types'

const fields: ResourceField<Customer>[] = [
  { key: 'name', label: 'Customer name', placeholder: 'Northstar Hosting', required: true },
  { key: 'account_reference', label: 'Reference', placeholder: 'CUST-0042' },
  { key: 'contact_name', label: 'Contact name', placeholder: 'Primary network contact' },
  { key: 'email', label: 'Email', type: 'email', placeholder: 'noc@example.com' },
  { key: 'phone', label: 'Phone', placeholder: '+964 …' },
  { key: 'notes', label: 'Notes', type: 'textarea', placeholder: 'Contract, allocation, or support context…', fullWidth: true },
]

const columns: ResourceColumn<Customer>[] = [
  { key: 'name', label: 'Customer', render: (item) => <div className="entity-cell"><span className="object-icon"><UsersRound size={16} /></span><span><strong>{item.name}</strong><small>{item.account_reference || 'No reference'}</small></span></div> },
  { key: 'contact', label: 'Contact', render: (item) => <><span className="table-primary">{item.contact_name || '—'}</span>{item.email && <small className="table-secondary inline-icon"><Mail size={12} /> {item.email}</small>}</> },
  { key: 'phone', label: 'Phone', render: (item) => item.phone || '—' },
  { key: 'addresses', label: 'Assigned IPs', render: (item) => <Badge tone={item.ip_count ? 'active' : 'neutral'}>{formatNumber(item.ip_count ?? 0)}</Badge> },
  { key: 'updated', label: 'Updated', render: (item) => formatDate(item.updated_at, false) },
]

export function CustomersPage() {
  return <ResourcePage<Customer> endpoint="/customers" noun="Customer" nounPlural="Customers" eyebrow="Allocation ownership" description="Keep customer contacts and address ownership clear at a glance." icon={UsersRound} fields={fields} columns={columns} />
}
