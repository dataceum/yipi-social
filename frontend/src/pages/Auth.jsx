import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { homeRouteFor } from '../utils'

function AuthLayout({ quote, who, children }) {
  return (
    <div className="auth-screen">
      <div className="auth-visual">
        <div className="logo">
          <span className="mark" />
          Yipi
        </div>
        <blockquote>“{quote}”</blockquote>
        <div className="who">{who}</div>
      </div>
      <div className="auth-form-side">
        <div className="auth-form-wrap">{children}</div>
      </div>
    </div>
  )
}

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const justSignedUp = location.state?.justSignedUp

  function update(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { me } = await login(form.username.trim(), form.password)
      // Admins/moderators land on the moderation queue, not the social feed.
      navigate(homeRouteFor(me), { replace: true })
    } catch (err) {
      setError(err.detail || 'Could not log in. Check your username and password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      quote="Yipi is where my group chat, my feed, and Friday night Spaces all live in one tab."
      who={
        <>
          <span className="avatar avatar-xs" style={{ background: 'rgba(255,255,255,0.3)' }} />
          an actual Yipi user
        </>
      }
    >
      <div>
        <h1>Welcome back</h1>
        <p className="sub">Log in to catch up on your feed.</p>
      </div>
      {justSignedUp && (
        <div className="form-alert" style={{ background: '#e7f7ef', color: 'var(--success)' }}>
          Account created — log in to get started.
        </div>
      )}
      <form className="auth-form" onSubmit={submit}>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input id="username" value={form.username} onChange={update('username')} autoFocus required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={form.password} onChange={update('password')} required />
        </div>
        {error && <div className="form-alert">{error}</div>}
        <button type="submit" className="btn btn-brand btn-block" disabled={busy}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      <div className="auth-switch">
        New to Yipi? <Link to="/signup">Create an account</Link>
      </div>
    </AuthLayout>
  )
}

const GENDERS = [
  ['male', 'Male'],
  ['female', 'Female'],
]

const EMPTY_SIGNUP = {
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  phone_number: '',
  birth_date: '',
  gender: 'female',
  password: '',
  confirm: '',
}

export function Signup() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY_SIGNUP)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function update(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await signup({
        username: form.username.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        phone_number: form.phone_number.trim(),
        birth_date: form.birth_date,
        gender: form.gender,
        password: form.password,
      })
      navigate('/login', { replace: true, state: { justSignedUp: true } })
    } catch (err) {
      setError(err.detail || 'Could not create your account. Double-check your details.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      quote="Signed up on my lunch break, was in a live Space by the time I finished eating."
      who={
        <>
          <span className="avatar avatar-xs" style={{ background: 'rgba(255,255,255,0.3)' }} />
          also an actual Yipi user
        </>
      }
    >
      <div>
        <h1>Create your account</h1>
        <p className="sub">Takes about a minute.</p>
      </div>
      <form className="auth-form" onSubmit={submit}>
        <div className="field-row">
          <div className="field">
            <label htmlFor="first_name">First name</label>
            <input id="first_name" value={form.first_name} onChange={update('first_name')} required minLength={2} />
          </div>
          <div className="field">
            <label htmlFor="last_name">Last name</label>
            <input id="last_name" value={form.last_name} onChange={update('last_name')} required minLength={2} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="username">Username</label>
          <input id="username" value={form.username} onChange={update('username')} required minLength={3} maxLength={20} />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={form.email} onChange={update('email')} required />
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="phone_number">Phone number</label>
            <input
              id="phone_number"
              value={form.phone_number}
              onChange={update('phone_number')}
              placeholder="+233201234567"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="birth_date">Birth date</label>
            <input id="birth_date" type="date" value={form.birth_date} onChange={update('birth_date')} required />
          </div>
        </div>
        <div className="field">
          <label htmlFor="gender">Gender</label>
          <select id="gender" value={form.gender} onChange={update('gender')}>
            {GENDERS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" value={form.password} onChange={update('password')} required minLength={8} />
          </div>
          <div className="field">
            <label htmlFor="confirm">Confirm password</label>
            <input id="confirm" type="password" value={form.confirm} onChange={update('confirm')} required minLength={8} />
          </div>
        </div>
        {error && <div className="form-alert">{error}</div>}
        <button type="submit" className="btn btn-brand btn-block" disabled={busy}>
          {busy ? 'Creating account…' : 'Sign up'}
        </button>
      </form>
      <div className="auth-switch">
        Already have an account? <Link to="/login">Log in</Link>
      </div>
    </AuthLayout>
  )
}
