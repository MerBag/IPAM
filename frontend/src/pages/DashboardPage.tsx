import { ArrowRight, Boxes, Globe2, Network, Plus, Server, ShieldCheck, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, ProgressBar, SkeletonRows, StatusBadge, TableContainer } from '../components/ui'
import { useApiData } from '../hooks/useApiData'
import { useAuth } from '../context/AuthContext'
import { formatDate, formatNumber, formatPercent, percentValue, titleCase } from '../lib/format'
import { unwrapList } from '../lib/api'
import type { Allocation, DashboardStats, Prefix } from '../types'

function statNumber(stats: DashboardStats, ...keys: (keyof DashboardStats)[]) {
  for (const key of keys) {
    const value = stats[key]
    if (typeof value === 'number') return value
  }
  return 0
}

function MetricCard({ label, value, detail, icon: Icon, tone }: { label: string; value: number; detail: string; icon: typeof Globe2; tone: string }) {
  return (
    <Card className="metric-card">
      <div className={`metric-card__icon metric-card__icon--${tone}`}><Icon size={20} /></div>
      <div className="metric-card__label">{label}</div>
      <div className="metric-card__value">{formatNumber(value)}</div>
      <div className="metric-card__detail">{detail}</div>
    </Card>
  )
}

function snapshotValue(item: Allocation, key: string) {
  const value = item.snapshot?.[key]
  return value === null || value === undefined ? '' : String(value)
}

function ipLabel(item: Allocation) {
  return snapshotValue(item, 'address') || `IP record #${item.ip_address_id}`
}

export function DashboardPage() {
  const { user } = useAuth()
  const readOnly = user?.role === 'read_only'
  const { data, loading, error, reload } = useApiData<DashboardStats>('/dashboard', {})
  const { data: prefixData } = useApiData<unknown>('/prefixes', [])
  const total = statNumber(data, 'total_ips')
  const assigned = statNumber(data, 'used_ips', 'assigned_ips')
  const free = statNumber(data, 'free_ips')
  const reserved = statNumber(data, 'reserved_ips')
  const subnetCount = statNumber(data, 'subnet_count', 'subnets')
  const deviceCount = statNumber(data, 'device_count', 'devices')
  const utilization = percentValue(data.utilization_percent ?? data.utilization ?? (total ? (assigned / total) * 100 : 0))
  const recent = data.recent_assignments || []
  const prefixes = unwrapList<Prefix>(prefixData)

  return (
    <div className="page">
      <PageHeader eyebrow="Network overview" title="Dashboard" description="Live allocation health across your managed IPv4 space." actions={<><Link to="/subnets"><Button variant="secondary"><Network size={16} /> Browse subnets</Button></Link>{!readOnly && <Link to="/ip-addresses"><Button><Plus size={16} /> Assign an IP</Button></Link>}</>} />
      {error && <ErrorState message={error} onRetry={reload} />}
      <div className="metrics-grid">
        <MetricCard label="Total addresses" value={total} detail="Across all prefixes" icon={Globe2} tone="blue" />
        <MetricCard label="Used" value={assigned} detail={`${formatPercent(utilization)} utilization`} icon={Server} tone="teal" />
        <MetricCard label="Available" value={free} detail="Ready to allocate" icon={Sparkles} tone="green" />
        <MetricCard label="Reserved" value={reserved} detail="Held from allocation" icon={ShieldCheck} tone="amber" />
      </div>
      <div className="dashboard-grid">
        <Card className="utilization-card">
          <div className="card-heading"><div><span className="eyebrow">Address utilization</span><h2>{formatPercent(utilization)} in use</h2></div><Badge tone={utilization >= 85 ? 'warning' : 'healthy'}>{utilization >= 85 ? 'Review capacity' : 'Healthy capacity'}</Badge></div>
          <div className="utilization-gauge">
            <div className="utilization-gauge__track" style={{ '--progress': `${utilization * 1.8}deg` } as React.CSSProperties}>
              <div><strong>{formatPercent(utilization)}</strong><span>unavailable</span></div>
            </div>
          </div>
          <div className="utilization-legend">
            <div><i className="dot dot--assigned" /><span>Used / unavailable</span><strong>{formatNumber(assigned)}</strong></div>
            <div><i className="dot dot--reserved" /><span>Reserved (included)</span><strong>{formatNumber(reserved)}</strong></div>
            <div><i className="dot dot--free" /><span>Free</span><strong>{formatNumber(free)}</strong></div>
          </div>
        </Card>
        <Card className="inventory-card">
          <div className="card-heading"><div><span className="eyebrow">Inventory</span><h2>Network objects</h2></div></div>
          <Link to="/prefixes" className="inventory-row"><span className="inventory-row__icon"><Boxes size={19} /></span><span><strong>{formatNumber(prefixes.length)}</strong><small>Managed prefixes</small></span><ArrowRight size={16} /></Link>
          <Link to="/subnets" className="inventory-row"><span className="inventory-row__icon"><Network size={19} /></span><span><strong>{formatNumber(subnetCount)}</strong><small>Managed subnets</small></span><ArrowRight size={16} /></Link>
          <Link to="/devices" className="inventory-row"><span className="inventory-row__icon"><Server size={19} /></span><span><strong>{formatNumber(deviceCount)}</strong><small>Tracked devices</small></span><ArrowRight size={16} /></Link>
        </Card>
      </div>
      <Card className="recent-card">
        <div className="card-heading card-heading--table"><div><span className="eyebrow">Latest activity</span><h2>Recent assignments</h2></div>{user?.role === 'admin' && <Link to="/audit-log" className="text-link">View audit log <ArrowRight size={14} /></Link>}</div>
        <TableContainer>
          <thead><tr><th>IP address</th><th>Status</th><th>Hostname / purpose</th><th>Customer</th><th>Assigned</th></tr></thead>
          {loading ? <SkeletonRows rows={5} columns={5} /> : (
            <tbody>
              {recent.map((item) => (
                <tr key={item.id}><td><Link className="mono-link" to={`/ip-addresses?search=${encodeURIComponent(ipLabel(item))}`}>{ipLabel(item)}</Link></td><td><StatusBadge status={item.new_status} /></td><td><strong className="table-primary">{snapshotValue(item, 'hostname') || snapshotValue(item, 'purpose') || titleCase(item.action)}</strong><small className="table-secondary">{snapshotValue(item, 'hostname') ? snapshotValue(item, 'purpose') : snapshotValue(item, 'device_id') ? `Device #${snapshotValue(item, 'device_id')}` : ''}</small></td><td>{snapshotValue(item, 'customer_id') ? `Customer #${snapshotValue(item, 'customer_id')}` : '—'}</td><td>{formatDate(item.created_at)}</td></tr>
              ))}
            </tbody>
          )}
        </TableContainer>
        {!loading && recent.length === 0 && <EmptyState title="No assignments yet" description="Your latest assigned IP addresses will appear here." action={!readOnly && <Link to="/ip-addresses"><Button size="small"><Plus size={14} /> Assign first IP</Button></Link>} />}
      </Card>
      {prefixes.length > 0 && (
        <div className="prefix-summary-grid">
          {prefixes.slice(0, 3).map((prefix: Prefix) => {
            const value = percentValue(prefix.utilization_percent ?? prefix.utilization)
            return <Card className="prefix-mini" key={prefix.id}><div><span>{prefix.name || 'IPv4 prefix'}</span><strong>{prefix.cidr}</strong></div><span>{formatPercent(value)}</span><ProgressBar value={value} /></Card>
          })}
        </div>
      )}
    </div>
  )
}
