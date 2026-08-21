import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { usersApi } from '../api'
import { Avatar } from '../components/ui'
import { Icon } from '../icons'

export default function Settings() {
  const { user, refreshUser } = useAuth()
  const [form, setForm] = useState({
    first_name: user?.first_name ?? '',
    last_name: user?.last_name ?? '',
    profile_picture_url: user?.profile?.profile_picture_url ?? '',
    bio_recording_url: user?.profile?.bio_recording_url ?? '',
    password: '',
    confirm: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  function update(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }))
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setSaved(false)

    if (form.password && form.password !== form.confirm) {
      setError('New passwords do not match.')
      return
    }

    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      profile_picture_url: form.profile_picture_url.trim() || null,
      bio_recording_url: form.bio_recording_url.trim() || null,
    }
    if (form.password) payload.password = form.password

    setBusy(true)
    try {
      await usersApi.update(user.id, payload)
      await refreshUser()
      setSaved(true)
      setForm((f) => ({ ...f, password: '', confirm: '' }))
    } catch (err) {
      setError(err.detail || 'Could not save your changes.')
    } finally {
      setBusy(false)
    }
  }

  if (!user) return null

  return (
    <div className="shell-content">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Manage your profile</p>
      </div>

      <form className="card settings-form" onSubmit={submit}>
        <div className="avatar-picker">
          <Avatar user={{ ...user, profile: { profile_picture_url: form.profile_picture_url } }} size="lg" />
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="profile_picture_url">Profile picture URL</label>
            <input
              id="profile_picture_url"
              value={form.profile_picture_url}
              onChange={update('profile_picture_url')}
              placeholder="https://…"
            />
          </div>
        </div>

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
          <label htmlFor="bio_recording_url">
            <Icon.Mic size={13} style={{ verticalAlign: '-2px', marginRight: 4 }} />
            Voice bio URL
          </label>
          <input
            id="bio_recording_url"
            value={form.bio_recording_url}
            onChange={update('bio_recording_url')}
            placeholder="Link to a short audio intro"
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="password">New password</label>
            <input id="password" type="password" value={form.password} onChange={update('password')} placeholder="Leave blank to keep current" minLength={8} />
          </div>
          <div className="field">
            <label htmlFor="confirm">Confirm new password</label>
            <input id="confirm" type="password" value={form.confirm} onChange={update('confirm')} minLength={8} />
          </div>
        </div>

        {error && <div className="form-alert">{error}</div>}
        {saved && (
          <div className="form-alert" style={{ background: '#e7f7ef', color: 'var(--success)' }}>
            Saved.
          </div>
        )}

        <button type="submit" className="btn btn-brand" style={{ alignSelf: 'flex-start' }} disabled={busy}>
          {busy ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <div className="card" style={{ padding: 'var(--space-5)' }}>
        <div className="row gap-3" style={{ fontSize: '0.9rem' }}>
          <span className="muted">Username</span>
          <span>@{user.username}</span>
        </div>
        <div className="row gap-3" style={{ fontSize: '0.9rem', marginTop: 8 }}>
          <span className="muted">Email</span>
          <span>{user.email}</span>
        </div>
      </div>
    </div>
  )
}
