import { BookOpenCheck, Filter, LogIn, Network, Search, ShieldCheck, UserRound, Waypoints } from 'lucide-react'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Badge, Card, EmptyState, ErrorState, Input, PageHeader, Pagination, Select, SkeletonRows, TableContainer } from '../components/ui'
import { useApiData } from '../hooks/useApiData'
import { queryString, unwrapList } from '../lib/api'
import { formatDate, titleCase } from '../lib/format'
import type { AuditLog, User } from '../types'
import { useAuth } from '../context/AuthContext'

function actionIcon(action: string) {
  if (/login/i.test(action)) return LogIn
  if (/subnet|prefix/i.test(action)) return Network
  if (/assign|release|ip/i.test(action)) return Waypoints
  return ShieldCheck
}

function actor(log: AuditLog, users: User[]) {
  if (typeof log.user === 'string') return log.user
  const knownUser = users.find((user) => String(user.id) === String(log.actor_id))
  return log.username || log.user?.full_name || log.user?.username || knownUser?.username || (log.actor_id ? `User #${log.actor_id}` : 'System')
}

function detailText(log: AuditLog) {
  if (log.description) return log.description
  const details = log.details || {}
  if (details.address) return `${details.address}${details.status ? ` · ${details.status}` : ''}`
  if (details.cidr) return String(details.cidr)
  return 'Recorded system activity'
}

export function AuditLogPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 50
  const path = `/audit-logs${queryString({ action, skip: (page - 1) * pageSize, limit: pageSize + 1 })}`
  const { data, loading, error, reload } = useApiData<unknown>(path, [])
  const { data: userData } = useApiData<unknown>('/users?limit=500', [])
  const users = unwrapList<User>(userData)
  const batch = unwrapList<AuditLog>(data)
  const hasNext = batch.length > pageSize
  const pageItems = batch.slice(0, pageSize)
  const items = search ? pageItems.filter((log) => `${log.action} ${actor(log, users)} ${log.entity_type || ''} ${log.source_ip || ''} ${detailText(log)}`.toLowerCase().includes(search.toLowerCase())) : pageItems
  const visibleTotal = (page - 1) * pageSize + items.length
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return (
    <div className="page">
      <PageHeader eyebrow="Accountability" title="Audit log" description="A durable record of authentication, inventory, subnet, and allocation changes." actions={<Badge tone="secure"><ShieldCheck size={13} /> History retained</Badge>} />
      {error && <ErrorState message={error} onRetry={reload} />}
      <Card>
        <div className="table-toolbar audit-toolbar">
          <div className="search-input"><Search size={16} /><Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} placeholder="Search actor, address, or event…" /></div>
          <div className="filter-select"><Filter size={15} /><Select value={action} onChange={(event) => { setAction(event.target.value); setPage(1) }} aria-label="Filter by action"><option value="">All activity</option><option value="ip_assigned">IP assigned</option><option value="ip_reserved">IP reserved</option><option value="ip_released">IP released</option><option value="ip_modified">IP modified</option><option value="subnet_created">Subnet created</option><option value="subnet_modified">Subnet modified</option><option value="subnet_deleted">Subnet deleted</option><option value="prefix_created">Prefix created</option><option value="prefix_modified">Prefix modified</option><option value="prefix_deleted">Prefix deleted</option><option value="device_created">Device created</option><option value="device_modified">Device modified</option><option value="device_deleted">Device deleted</option><option value="customer_created">Customer created</option><option value="customer_modified">Customer modified</option><option value="customer_deleted">Customer deleted</option><option value="router_created">Router created</option><option value="router_modified">Router modified</option><option value="router_deleted">Router deleted</option><option value="user_created">User created</option><option value="user_modified">User modified</option><option value="login">User login</option><option value="login_failed">Failed login</option></Select></div>
        </div>
        <TableContainer>
          <thead><tr><th>Event</th><th>Actor</th><th>Resource</th><th>Source IP</th><th>Time</th></tr></thead>
          {loading ? <SkeletonRows rows={8} columns={5} /> : (
            <tbody>
              {items.map((log) => {
                const Icon = actionIcon(log.action)
                return (
                  <tr key={log.id}>
                    <td><div className="audit-event"><span className="audit-event__icon"><Icon size={16} /></span><span><strong>{titleCase(log.action)}</strong><small>{detailText(log)}</small></span></div></td>
                    <td><span className="actor-cell"><span className="avatar avatar--small"><UserRound size={13} /></span>{actor(log, users)}</span></td>
                    <td>{log.entity_type ? <><span className="table-primary">{titleCase(log.entity_type)}</span>{log.entity_id && <small className="table-secondary">ID {log.entity_id}</small>}</> : '—'}</td>
                    <td><span className="mono text-small">{log.source_ip || log.ip_address || '—'}</span></td>
                    <td>{formatDate(log.created_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          )}
        </TableContainer>
        {!loading && !items.length && <EmptyState icon={BookOpenCheck} title="No activity found" description={search || action ? 'Adjust the filters to see other events.' : 'Audited changes will appear here as people use merbag IPAM.'} />}
        <Pagination page={page} pages={hasNext ? page + 1 : page} total={visibleTotal} pageSize={pageSize} hasNext={hasNext} totalExact={false} onPageChange={setPage} />
      </Card>
    </div>
  )
}
