import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { useAuth } from './context/AuthContext'
import { AuditLogPage } from './pages/AuditLogPage'
import { CustomersPage } from './pages/CustomersPage'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { IpAddressesPage } from './pages/IpAddressesPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PrefixesPage } from './pages/PrefixesPage'
import { RoutersPage } from './pages/RoutersPage'
import { SettingsPage } from './pages/SettingsPage'
import { SubnetsPage } from './pages/SubnetsPage'

function ProtectedLayout() {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="app-loading">
        <span className="brand-mark brand-mark--large"><span className="app-loading__pulse" /></span>
        <strong>merbag IPAM application</strong>
        <small>Loading your workspace…</small>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return <AppShell />
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="prefixes" element={<PrefixesPage />} />
        <Route path="subnets" element={<SubnetsPage />} />
        <Route path="ip-addresses" element={<IpAddressesPage />} />
        <Route path="devices" element={<DevicesPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="routers" element={<RoutersPage />} />
        <Route path="audit-log" element={<AuditLogPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
