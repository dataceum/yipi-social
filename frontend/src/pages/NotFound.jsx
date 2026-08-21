import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div
      className="stack gap-4"
      style={{ minHeight: '100vh', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 'var(--space-5)' }}
    >
      <div className="landing-logo">
        <span className="mark" />
        Yipi
      </div>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '2.4rem' }}>Page not found</h1>
      <p className="muted">That link doesn't lead anywhere on Yipi.</p>
      <Link to="/" className="btn btn-brand">
        Go home
      </Link>
    </div>
  )
}
