import {
  Activity,
  BookOpenCheck,
  Boxes,
  ChevronDown,
  CircleGauge,
  Globe2,
  LogOut,
  Menu,
  Moon,
  Network,
  PanelLeftClose,
  Router,
  Server,
  Settings,
  Sun,
  UsersRound,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { initials, titleCase } from '../lib/format'
import { applyTheme, getActiveTheme, type Theme } from '../lib/theme'
import { GlobalSearch } from './GlobalSearch'

const navItems = [
  { to: '/', label: 'Dashboard', icon: CircleGauge, end: true },
  { to: '/prefixes', label: 'Prefixes', icon: Boxes },
  { to: '/subnets', label: 'Subnets', icon: Network },
  { to: '/ip-addresses', label: 'IP Addresses', icon: Globe2 },
  { to: '/devices', label: 'Devices', icon: Server },
  { to: '/customers', label: 'Customers', icon: UsersRound },
  { to: '/routers', label: 'Routers', icon: Router },
]

const systemItems = [
  { to: '/audit-log', label: 'Audit Log', icon: BookOpenCheck },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function SidebarLink({ item, onClick }: { item: (typeof navItems)[number]; onClick?: () => void }) {
  const Icon = item.icon
  return (
    <NavLink to={item.to} end={'end' in item && item.end} onClick={onClick} className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}>
      <Icon size={19} />
      <span>{item.label}</span>
    </NavLink>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('merbag.sidebar') === 'collapsed')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [theme, setTheme] = useState<Theme>(getActiveTheme)
  const location = useLocation()

  useEffect(() => setMobileOpen(false), [location.pathname])
  useEffect(() => localStorage.setItem('merbag.sidebar', collapsed ? 'collapsed' : 'expanded'), [collapsed])

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light'
    applyTheme(nextTheme)
    setTheme(nextTheme)
  }

  const displayName = user?.full_name || user?.username || 'merbag IPAM user'
  return (
    <div className={`app-shell ${collapsed ? 'app-shell--collapsed' : ''}`}>
      {mobileOpen && <button type="button" className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar--mobile-open' : ''}`}>
        <div className="sidebar__brand">
          <span className="brand-mark"><Network size={22} strokeWidth={2.4} /></span>
          <span className="brand-copy"><strong>merbag</strong><small>IPAM APPLICATION</small></span>
          <button type="button" className="icon-button sidebar__mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={19} /></button>
        </div>
        <div className="sidebar__environment"><span className="status-pulse" /><span>Local network</span></div>
        <nav className="sidebar__nav" aria-label="Primary navigation">
          <span className="sidebar__section-label">Workspace</span>
          {navItems.map((item) => <SidebarLink item={item} key={item.to} onClick={() => setMobileOpen(false)} />)}
          <span className="sidebar__section-label sidebar__section-label--spaced">System</span>
          {systemItems.filter((item) => item.to !== '/audit-log' || user?.role === 'admin').map((item) => <SidebarLink item={item} key={item.to} onClick={() => setMobileOpen(false)} />)}
        </nav>
        <div className="sidebar__footer">
          <div className="sidebar__health"><Activity size={15} /><span>API connected</span><i /></div>
          <button type="button" className="sidebar__collapse" onClick={() => setCollapsed((value) => !value)} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            <PanelLeftClose size={17} /> <span>Collapse</span>
          </button>
        </div>
      </aside>
      <div className="app-frame">
        <header className="topbar">
          <button type="button" className="icon-button topbar__menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
          <GlobalSearch />
          <div className="topbar__account-actions">
            <button
              type="button"
              className="icon-button theme-toggle"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
              aria-pressed={theme === 'dark'}
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
            </button>
            <div className="account-menu">
              <button type="button" className="account-menu__trigger" onClick={() => setAccountOpen((value) => !value)} aria-expanded={accountOpen}>
                <span className="avatar">{initials(displayName)}</span>
                <span className="account-menu__copy"><strong>{displayName}</strong><small>{titleCase(user?.role || 'user')}</small></span>
                <ChevronDown size={15} />
              </button>
              {accountOpen && (
                <div className="account-popover">
                  <div><strong>{displayName}</strong><small>{user?.email || `@${user?.username}`}</small></div>
                  <button type="button" onClick={logout}><LogOut size={16} /> Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="main-content"><Outlet /></main>
      </div>
    </div>
  )
}
