import { ArrowRight, Eye, EyeOff, LockKeyhole, Network, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Button, Field, Input } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export function LoginPage() {
  const { user, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const location = useLocation()
  const navigate = useNavigate()
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/'

  useEffect(() => document.getElementById('username')?.focus(), [])
  if (user) return <Navigate to="/" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!username.trim() || !password) {
      setError('Enter both your username and password.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      await login(username.trim(), password)
      navigate(from, { replace: true })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to sign in. Check your credentials and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="login-story__inner">
          <div className="login-brand"><span className="brand-mark"><Network size={22} /></span><span><strong>merbag</strong><small>IPAM APPLICATION</small></span></div>
          <div className="login-story__copy">
            <span className="login-kicker"><ShieldCheck size={15} /> Local network control plane</span>
            <h1>Every address.<br />Exactly where it belongs.</h1>
            <p>Plan subnets, assign public IPv4 space, and keep a complete operational history from one focused workspace.</p>
          </div>
          <div className="login-story__footer"><span className="status-pulse" /> Your data stays on your infrastructure</div>
        </div>
      </section>
      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <div className="login-form__mobile-brand"><span className="brand-mark"><Network size={21} /></span><strong>merbag IPAM application</strong></div>
          <div className="login-form__heading">
            <h2>Welcome back</h2>
            <p>Sign in to your network workspace.</p>
          </div>
          {error && <div className="form-alert" role="alert">{error}</div>}
          <Field label="Username" required>
            <Input id="username" name="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Enter your username" disabled={submitting} />
          </Field>
          <Field label="Password" required>
            <div className="password-input">
              <Input name="password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" disabled={submitting} />
              <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button>
            </div>
          </Field>
          <Button className="login-form__submit" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'} {!submitting && <ArrowRight size={17} />}
          </Button>
          <div className="login-security"><LockKeyhole size={15} /><span>Your password is used only for this sign-in request and is never stored in this page.</span></div>
        </form>
        <span className="login-version">merbag IPAM application · Local deployment</span>
      </section>
    </main>
  )
}
