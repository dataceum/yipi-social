import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { usersApi } from '../api'
import { Avatar, Spinner, EmptyState } from '../components/ui'
import { Icon } from '../icons'
import { fullName } from '../utils'

export default function Search() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 3) {
      setResults(null)
      return
    }
    setLoading(true)
    const handle = setTimeout(async () => {
      try {
        const res = await usersApi.search(q)
        setResults(res.results)
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(handle)
  }, [query])

  return (
    <div className="shell-content">
      <div className="page-header">
        <h1>Search</h1>
      </div>

      <div className="card" style={{ padding: 'var(--space-4)' }}>
        <div className="field">
          <div className="row" style={{ position: 'relative' }}>
            <Icon.Search size={17} style={{ position: 'absolute', left: 14, color: 'var(--text-faint)' }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by username, email, or phone"
              style={{ paddingLeft: 40 }}
              autoFocus
            />
          </div>
        </div>
      </div>

      {loading && <Spinner page />}

      {!loading && query.trim().length >= 3 && results?.length === 0 && (
        <div className="card">
          <EmptyState icon="🔎" title="No one found" description={`Nothing matched "${query.trim()}".`} />
        </div>
      )}

      {!loading && results?.length > 0 && (
        <div className="card" style={{ overflow: 'hidden' }}>
          {results.map((u, i) => (
            <Link
              to={`/profile/${u.id}`}
              key={u.id}
              className="row gap-3"
              style={{ padding: 'var(--space-4)', borderTop: i > 0 ? '1px solid var(--border)' : 'none' }}
            >
              <Avatar user={u} size="md" />
              <div>
                <div style={{ fontWeight: 700 }}>{fullName(u)}</div>
                <div className="faint">@{u.username}</div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {!loading && query.trim().length > 0 && query.trim().length < 3 && (
        <p className="muted" style={{ textAlign: 'center' }}>
          Keep typing — at least 3 characters.
        </p>
      )}
    </div>
  )
}
