import { Activity, Check, Database, KeyRound, LogOut, Network, Plus, ShieldCheck, UserRound, UsersRound } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select, TableContainer } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useApiData } from '../hooks/useApiData'
import { request, unwrapList } from '../lib/api'
import { formatDate, initials, titleCase } from '../lib/format'
import type { User } from '../types'

function AddUserDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('read_only')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const { notify } = useToast()
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await request('/users', { method: 'POST', body: { username: username.trim(), password, role, is_active: true } })
      notify(`Created user ${username.trim()}.`)
      onCreated()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to create user.')
    } finally {
      setSaving(false)
    }
  }
  return (
    <Modal title="Add local user" description="Create a named account with the minimum access it needs." onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        {error && <div className="form-alert" role="alert">{error}</div>}
        <Field label="Username" required hint="Letters, numbers, periods, underscores, and hyphens."><Input autoFocus value={username} onChange={(event) => setUsername(event.target.value)} minLength={3} pattern="[A-Za-z0-9_.-]+" required /></Field>
        <Field label="Temporary password" required hint="At least 12 characters. Share it through a secure channel."><Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} autoComplete="new-password" required /></Field>
        <Field label="Role" required><Select value={role} onChange={(event) => setRole(event.target.value)}><option value="read_only">Read Only</option><option value="operator">Operator</option><option value="admin">Admin</option></Select></Field>
        <div className="modal__actions"><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Creating…' : 'Create user'}</Button></div>
      </form>
    </Modal>
  )
}

function UserManagement() {
  const { data, loading, error, reload } = useApiData<unknown>('/users', [])
  const [addOpen, setAddOpen] = useState(false)
  const [updating, setUpdating] = useState<string | null>(null)
  const { notify } = useToast()
  const users = unwrapList<User>(data)
  const update = async (target: User, patch: { role?: string; is_active?: boolean }) => {
    setUpdating(String(target.id))
    try {
      await request(`/users/${target.id}`, { method: 'PATCH', body: patch })
      notify(`Updated ${target.username}.`)
      reload()
    } catch (reason) {
      notify(reason instanceof Error ? reason.message : 'Unable to update user.', 'error')
    } finally {
      setUpdating(null)
    }
  }
  return (
    <Card className="role-card user-management">
      <div className="user-management__header"><div className="settings-card__heading"><span className="settings-icon"><UsersRound size={19} /></span><div><h2>Local users</h2><p>Create accounts and apply least-privilege roles.</p></div></div><Button size="small" onClick={() => setAddOpen(true)}><Plus size={14} /> Add user</Button></div>
      {error && <div className="form-alert">{error}</div>}
      {!loading && !users.length ? <EmptyState icon={UsersRound} title="No users returned" description="Create the first managed account." /> : (
        <TableContainer><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Last login</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}><td><div className="actor-cell"><span className="avatar avatar--small">{initials(item.username)}</span><strong>{item.username}</strong></div></td><td><Select value={item.role || 'read_only'} disabled={updating === String(item.id)} onChange={(event) => void update(item, { role: event.target.value })}><option value="read_only">Read Only</option><option value="operator">Operator</option><option value="admin">Admin</option></Select></td><td><button type="button" className={`status-toggle ${item.is_active !== false ? 'status-toggle--active' : ''}`} disabled={updating === String(item.id)} onClick={() => void update(item, { is_active: item.is_active === false })}><span />{item.is_active !== false ? 'Active' : 'Disabled'}</button></td><td>{formatDate(item.last_login_at)}</td></tr>)}</tbody></TableContainer>
      )}
      {addOpen && <AddUserDialog onClose={() => setAddOpen(false)} onCreated={reload} />}
    </Card>
  )
}

export function SettingsPage() {
  const { user, logout } = useAuth()
  const [compact, setCompact] = useState(() => localStorage.getItem('merbag.density') === 'compact')
  useEffect(() => {
    document.body.classList.toggle('density-compact', compact)
    localStorage.setItem('merbag.density', compact ? 'compact' : 'comfortable')
    return () => document.body.classList.remove('density-compact')
  }, [compact])
  const displayName = user?.full_name || user?.username || 'merbag IPAM user'
  return (
    <div className="page">
      <PageHeader eyebrow="Workspace preferences" title="Settings" description="Review your access level, local display preferences, and application connection." />
      <div className="settings-grid">
        <Card className="settings-card settings-card--profile">
          <div className="settings-card__heading"><span className="settings-icon"><UserRound size={19} /></span><div><h2>Your account</h2><p>Identity supplied by merbag IPAM authentication.</p></div></div>
          <div className="profile-block"><span className="avatar avatar--large">{initials(displayName)}</span><div><strong>{displayName}</strong><span>@{user?.username}</span></div><Badge tone="active">{titleCase(user?.role || 'user')}</Badge></div>
          <div className="settings-facts"><div><span>Email</span><strong>{user?.email || 'Not set'}</strong></div><div><span>User ID</span><strong className="mono">{user?.id || '—'}</strong></div></div>
        </Card>
        <Card className="settings-card">
          <div className="settings-card__heading"><span className="settings-icon"><Network size={19} /></span><div><h2>Display</h2><p>Preferences are saved only in this browser.</p></div></div>
          <label className="setting-row"><span><strong>Compact tables</strong><small>Fit more address records on screen.</small></span><input className="toggle" type="checkbox" checked={compact} onChange={(event) => setCompact(event.target.checked)} /></label>
          <div className="setting-row"><span><strong>Address notation</strong><small>IPv4 addresses and CIDRs use monospace type.</small></span><Badge tone="neutral"><Check size={12} /> Enabled</Badge></div>
        </Card>
        <Card className="settings-card">
          <div className="settings-card__heading"><span className="settings-icon"><Activity size={19} /></span><div><h2>Connection</h2><p>Browser-to-server API configuration.</p></div></div>
          <div className="connection-row"><span className="status-pulse" /><div><strong>merbag IPAM API</strong><small>Relative endpoint · /api</small></div><Badge tone="healthy">Connected</Badge></div>
          <div className="connection-row"><Database size={17} /><div><strong>Database</strong><small>Protected behind the backend service</small></div><Badge tone="secure"><ShieldCheck size={12} /> Private</Badge></div>
        </Card>
        <Card className="settings-card">
          <div className="settings-card__heading"><span className="settings-icon"><KeyRound size={19} /></span><div><h2>Session</h2><p>Secure this browser when you are finished.</p></div></div>
          <div className="session-copy">Signing out removes the local access token. It does not change your account or audit history.</div>
          <Button variant="secondary" onClick={logout}><LogOut size={15} /> Sign out of merbag IPAM</Button>
        </Card>
      </div>
      <Card className="role-card">
        <div className="settings-card__heading"><span className="settings-icon"><ShieldCheck size={19} /></span><div><h2>Role capabilities</h2><p>Permissions are enforced by the API, not only by interface controls.</p></div></div>
        <div className="role-grid"><div><Badge tone="active">Admin</Badge><span>Full inventory, allocation, user, and system administration.</span></div><div><Badge tone="neutral">Operator</Badge><span>Manage prefixes, subnets, addresses, devices, customers, and routers.</span></div><div><Badge tone="neutral">Read Only</Badge><span>View and search inventory without changing records.</span></div></div>
      </Card>
      {user?.role === 'admin' && <UserManagement />}
    </div>
  )
}
