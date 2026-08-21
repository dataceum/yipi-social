import { useEffect } from 'react'
import { initials, avatarHue } from '../utils'
import { Icon } from '../icons'

export function Avatar({ user, src, size = 'md', ring = false, style, ...rest }) {
  const url = src ?? user?.profile?.profile_picture_url
  const hue = avatarHue(user?.username ?? user?.id)
  const gradient = { background: `linear-gradient(135deg, hsl(${hue} 80% 62%), hsl(${(hue + 45) % 360} 75% 55%))` }

  return (
    <div
      className={`avatar avatar-${size}`}
      style={{ ...(url ? {} : gradient), ...(ring ? { boxShadow: '0 0 0 3px var(--accent-soft)' } : {}), ...style }}
      {...rest}
    >
      {url ? (
        <img src={url} alt="" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
      ) : (
        initials(user)
      )}
    </div>
  )
}

export function Spinner({ page = false }) {
  if (page) {
    return (
      <div className="spinner-page">
        <div className="spinner" />
      </div>
    )
  }
  return <div className="spinner" />
}

export function EmptyState({ icon = '✨', title, description, action }) {
  return (
    <div className="empty-state">
      <div className="icon">{icon}</div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}

export function Badge({ children, tone = 'default' }) {
  const cls = tone === 'live' ? 'badge badge-live' : tone === 'accent' ? 'badge badge-accent' : 'badge'
  return <span className={cls}>{children}</span>
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <h3>{title}</h3>
          <button className="btn-icon" onClick={onClose} aria-label="Close">
            <Icon.X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Toast({ message }) {
  if (!message) return null
  return <div className="toast">{message}</div>
}
