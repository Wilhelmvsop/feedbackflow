import { useState, type FormEvent } from 'react'
import { ArrowRight, Layers2 } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { errorMessage } from '../lib/format'

const DEMO_EMAIL = 'demo@feedbackflow.local'

export function LoginPage() {
  const { signIn } = useAuth()
  const [email, setEmail] = useState(DEMO_EMAIL)
  // Only prefill the well-known local password in development builds.
  const [password, setPassword] = useState(import.meta.env.DEV ? 'feedbackflow-demo' : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await signIn(email, password)
    } catch (e) {
      setError(errorMessage(e))
      setBusy(false)
    }
  }

  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-mark"><Layers2 size={22} /></div>
        <p className="eyebrow">FEEDBACKFLOW WORKSPACE</p>
        <h1>Turn feedback into<br />work that ships.</h1>
        <p className="muted">Sign in to triage feedback and shape the next release.</p>
        <label>Email<input value={email} onChange={e => setEmail(e.target.value)} type="email" autoComplete="username" required /></label>
        <label>Password<input value={password} onChange={e => setPassword(e.target.value)} type="password" autoComplete="current-password" required /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="primary wide" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<ArrowRight size={16} /></button>
        <p className="login-hint">Demo access · {DEMO_EMAIL}</p>
      </form>
      <div className="login-foot">A calmer way to listen, decide, and deliver.</div>
    </main>
  )
}
