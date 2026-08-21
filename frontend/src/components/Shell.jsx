import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { Avatar } from './ui'
import { Icon } from '../icons'
import { fullName, isReviewer } from '../utils'
import ComposeModal from './ComposeModal'

const SOCIAL_NAV = [
  { to: '/feed', label: 'Home', icon: Icon.Home },
  { to: '/search', label: 'Search', icon: Icon.Search },
  { to: '/rooms', label: 'Spaces', icon: Icon.Spaces },
  { to: '/settings', label: 'Settings', icon: Icon.Settings },
]

const MODERATION_LINK = { to: '/moderation', label: 'Moderation', icon: Icon.Flag }

export default function Shell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [composing, setComposing] = useState(false)
  const reviewer = isReviewer(user)
  // Reviewers get Moderation pinned right after Home — it's their primary
  // queue, not an afterthought buried past the social nav.
  const NAV = reviewer
    ? [SOCIAL_NAV[0], MODERATION_LINK, ...SOCIAL_NAV.slice(1)]
    : SOCIAL_NAV

  async function handleLogout() {
    await logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="shell">
      <aside className="shell-sidebar">
        <div className="shell-logo">
          <span className="mark" />
          Yipi
        </div>

        <nav className="shell-nav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `shell-nav-link${isActive ? ' active' : ''}`}
            >
              <span className="ico">
                <item.icon size={21} />
              </span>
              {item.label}
            </NavLink>
          ))}
          {user && (
            <NavLink
              to={`/profile/${user.id}`}
              className={({ isActive }) => `shell-nav-link${isActive ? ' active' : ''}`}
            >
              <span className="ico">
                <Icon.User size={21} />
              </span>
              Profile
            </NavLink>
          )}
        </nav>

        <button className="btn btn-brand btn-block shell-compose" onClick={() => setComposing(true)}>
          <Icon.Plus size={17} />
          Post
        </button>

        {user && (
          <div className="shell-user">
            <Avatar user={user} size="sm" />
            <div className="shell-user-meta">
              <div className="name truncate">{fullName(user)}</div>
              <div className="handle truncate">@{user.username}</div>
            </div>
            <button className="btn-icon" onClick={handleLogout} title="Log out" aria-label="Log out">
              <Icon.LogOut size={18} />
            </button>
          </div>
        )}
      </aside>

      <div className="mobile-topbar">
        <div className="shell-logo">
          <span className="mark" />
          Yipi
        </div>
        <button className="btn-icon" onClick={() => setComposing(true)} aria-label="New post">
          <Icon.Plus size={20} />
        </button>
      </div>

      <main className="shell-main">
        <Outlet />
      </main>

      <nav className="mobile-tabbar">
        {NAV.filter((n) => n.to !== '/settings').map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')}>
            <item.icon size={22} />
          </NavLink>
        ))}
        {user && (
          <NavLink to={`/profile/${user.id}`} className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon.User size={22} />
          </NavLink>
        )}
      </nav>

      {composing && <ComposeModal onClose={() => setComposing(false)} />}
    </div>
  )
}
