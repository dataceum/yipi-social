export function initials(user) {
  if (!user) return '?'
  const a = user.first_name?.[0] ?? user.username?.[0] ?? '?'
  const b = user.last_name?.[0] ?? ''
  return (a + b).toUpperCase()
}

export function fullName(user) {
  if (!user) return 'Someone'
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ')
  return name || user.username
}

/** A deterministic hue from a name so avatars without a picture still look
 * distinct from one another instead of all sharing the exact same gradient. */
export function avatarHue(seed) {
  const s = String(seed ?? '')
  let hash = 0
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0
  return hash % 360
}

export function relativeTime(dateString) {
  const date = new Date(dateString)
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 5) return 'now'
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function formatCount(n) {
  if (!n) return ''
  if (n < 1000) return String(n)
  if (n < 1_000_000) return `${(n / 1000).toFixed(n % 1000 >= 100 ? 1 : 0)}K`
  return `${(n / 1_000_000).toFixed(1)}M`
}

/** Mirrors the backend's own reviewer check (see `_is_reviewer` in
 * posts.py/rooms.py/reports.py etc.) — admins and moderators both review
 * reports, so both land on the moderation queue rather than the feed. */
export function isReviewer(user) {
  return user?.role === 'admin' || user?.role === 'moderator'
}

export function homeRouteFor(user) {
  return isReviewer(user) ? '/moderation' : '/feed'
}
