import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { authToken, request } from '../lib/api'
import type { User } from '../types'

type AuthState = {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => Boolean(authToken.get()))

  const logout = useCallback(() => {
    authToken.clear()
    setUser(null)
    setLoading(false)
  }, [])

  useEffect(() => {
    const onUnauthorized = () => logout()
    window.addEventListener('merbag:unauthorized', onUnauthorized)
    return () => window.removeEventListener('merbag:unauthorized', onUnauthorized)
  }, [logout])

  useEffect(() => {
    if (!authToken.get()) {
      setLoading(false)
      return
    }
    let active = true
    request<User>('/auth/me')
      .then((nextUser) => active && setUser(nextUser))
      .catch(() => active && logout())
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [logout])

  const login = useCallback(async (username: string, password: string) => {
    const result = await request<{ access_token?: string; token?: string; user?: User }>('/auth/login', {
      method: 'POST',
      body: { username, password },
    })
    const token = result.access_token || result.token
    if (!token) throw new Error('The server did not return an access token.')
    authToken.set(token)
    const nextUser = result.user || (await request<User>('/auth/me'))
    setUser(nextUser)
  }, [])

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
