import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { reportsApi, postsApi, roomsApi, usersApi } from '../api'
import { Avatar, Spinner, EmptyState, Badge } from '../components/ui'
import { Icon } from '../icons'
import { fullName, relativeTime } from '../utils'

const SECTIONS = [
  ['approvals', 'Profile approvals'],
  ['reports', 'Reports'],
]

export default function Moderation() {
  const [section, setSection] = useState('approvals')
  // Pending counts badge each section tab so a moderator sees what needs
  // attention without opening it — refetched whenever a panel resolves
  // something, via the bump counter.
  const [counts, setCounts] = useState({ approvals: null, reports: null })
  const [bump, setBump] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function loadCounts() {
      const [approvals, reports] = await Promise.all([
        usersApi.search({ profileStatus: 'pending', limit: 1 }),
        reportsApi.list({ status: 'pending', limit: 1 }),
      ])
      if (!cancelled) {
        setCounts({ approvals: approvals.total_count, reports: reports.total_count })
      }
    }
    loadCounts()
    return () => {
      cancelled = true
    }
  }, [bump])

  const refreshCounts = useCallback(() => setBump((n) => n + 1), [])

  return (
    <div className="shell-content wide">
      <div className="page-header">
        <div>
          <h1>Moderation</h1>
          <p>Profile approvals and content reports</p>
        </div>
      </div>

      <div className="room-filter-row">
        {SECTIONS.map(([value, label]) => (
          <button key={value} className={section === value ? 'active' : ''} onClick={() => setSection(value)}>
            {label}
            {!!counts[value] && (
              <span style={{ marginLeft: 8 }}>
                <Badge tone="accent">{counts[value]}</Badge>
              </span>
            )}
          </button>
        ))}
      </div>

      {section === 'approvals' ? <ApprovalsPanel onResolved={refreshCounts} /> : <ReportsPanel onResolved={refreshCounts} />}
    </div>
  )
}

/* =========================================================================
   Profile approvals — the main day-to-day queue: new signups sit at
   Profile.status = PENDING (see backend/app/api/v1/endpoints/auth.py
   signup()) until a moderator approves or rejects them.
   ========================================================================= */

const PROFILE_STATUS_TABS = [
  ['pending', 'Pending'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  ['suspended', 'Suspended'],
  ['inactive', 'Inactive'],
]

function ApprovalsPanel({ onResolved }) {
  const [tab, setTab] = useState('pending')
  const [users, setUsers] = useState(null)
  const [openId, setOpenId] = useState(null)

  const load = useCallback(async () => {
    setUsers(null)
    const res = await usersApi.search({ profileStatus: tab, limit: 50 })
    setUsers(res.results)
  }, [tab])

  useEffect(() => {
    load()
  }, [load])

  function handleUpdated(userId, updated) {
    onResolved()
    if (updated.profile?.status !== tab) {
      setUsers((prev) => prev.filter((u) => u.id !== userId))
    } else {
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)))
    }
  }

  return (
    <>
      <div className="room-filter-row">
        {PROFILE_STATUS_TABS.map(([value, label]) => (
          <button key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>
            {label}
          </button>
        ))}
      </div>

      {users === null ? (
        <Spinner page />
      ) : users.length === 0 ? (
        <div className="card">
          <EmptyState icon="🪪" title="Nothing here" description={`No ${PROFILE_STATUS_TABS.find(([v]) => v === tab)?.[1].toLowerCase()} profiles right now.`} />
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          {users.map((u, i) => (
            <div key={u.id} style={i > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
              <ApprovalRow
                profileUser={u}
                open={openId === u.id}
                onToggle={() => setOpenId((id) => (id === u.id ? null : u.id))}
                onUpdated={(updated) => handleUpdated(u.id, updated)}
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}

const REJECTION_REASONS = [
  ['inappropriate content', 'Inappropriate content'],
  ['copyright violation', 'Copyright violation'],
  ['criminal activity', 'Criminal activity'],
]

function ApprovalRow({ profileUser, open, onToggle, onUpdated }) {
  const profile = profileUser.profile
  const [busy, setBusy] = useState(false)
  const [rejecting, setRejecting] = useState(false)
  const [reason, setReason] = useState(profile?.reason ?? REJECTION_REASONS[0][0])
  const [comment, setComment] = useState(profile?.comment ?? '')

  async function approve() {
    setBusy(true)
    try {
      const updated = await usersApi.update(profileUser.id, { status: 'approved' })
      onUpdated(updated)
    } finally {
      setBusy(false)
    }
  }

  async function reject() {
    setBusy(true)
    try {
      const updated = await usersApi.update(profileUser.id, {
        status: 'rejected',
        reason,
        comment: comment.trim() || undefined,
      })
      setRejecting(false)
      onUpdated(updated)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ padding: 'var(--space-4)' }}>
      <div className="row gap-3" style={{ cursor: 'pointer' }} onClick={onToggle}>
        <Avatar user={profileUser} size="md" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: '0.92rem' }}>{fullName(profileUser)}</span>
            <span className="faint" style={{ fontSize: '0.84rem' }}>@{profileUser.username}</span>
            {profile?.age_category && <Badge>{profile.age_category}</Badge>}
          </div>
          <div className="faint" style={{ fontSize: '0.8rem', marginTop: 2 }}>
            {profile?.date_created ? `Submitted ${relativeTime(profile.date_created)}` : null}
            {profileUser.email ? ` · ${profileUser.email}` : ''}
          </div>
        </div>
        <Icon.ChevronLeft size={16} style={{ transform: open ? 'rotate(90deg)' : 'rotate(-90deg)', flexShrink: 0 }} />
      </div>

      {open && (
        <div className="stack gap-3" style={{ marginTop: 'var(--space-3)', paddingLeft: 56 }}>
          <div className="card" style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--bg-sunken)', border: 'none' }}>
            <div className="row gap-4" style={{ flexWrap: 'wrap', fontSize: '0.86rem' }}>
              {profileUser.phone_number && (
                <span>
                  <span className="faint">Phone: </span>
                  {profileUser.phone_number}
                </span>
              )}
              {profileUser.gender && (
                <span>
                  <span className="faint">Gender: </span>
                  {profileUser.gender}
                </span>
              )}
              {profileUser.birth_date && (
                <span>
                  <span className="faint">Born: </span>
                  {profileUser.birth_date}
                </span>
              )}
            </div>

            {profile?.bio_recording_url ? (
              <div style={{ marginTop: 10 }}>
                <span className="faint" style={{ fontSize: '0.8rem' }}>Voice bio</span>
                <audio controls src={profile.bio_recording_url} style={{ width: '100%', marginTop: 4 }} />
              </div>
            ) : (
              <p className="faint" style={{ fontSize: '0.84rem', marginTop: 10 }}>No voice bio provided.</p>
            )}

            {(profile?.reason || profile?.comment) && (
              <div style={{ marginTop: 10, fontSize: '0.84rem' }}>
                <Badge tone="live">previous decision</Badge>
                {profile?.reason && <p style={{ marginTop: 4 }}>Reason: {REJECTION_REASONS.find(([v]) => v === profile.reason)?.[1] ?? profile.reason}</p>}
                {profile?.comment && <p style={{ marginTop: 4 }}>“{profile.comment}”</p>}
              </div>
            )}
          </div>

          {rejecting ? (
            <div className="stack gap-3">
              <div className="field">
                <label htmlFor={`reason-${profileUser.id}`}>Rejection reason</label>
                <select id={`reason-${profileUser.id}`} value={reason} onChange={(e) => setReason(e.target.value)}>
                  {REJECTION_REASONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor={`comment-${profileUser.id}`}>Note (optional)</label>
                <textarea
                  id={`comment-${profileUser.id}`}
                  rows={2}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Why this decision, for the record"
                />
              </div>
              <div className="row gap-2">
                <button className="btn btn-danger btn-sm" disabled={busy} onClick={reject}>
                  {busy ? 'Rejecting…' : 'Confirm rejection'}
                </button>
                <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setRejecting(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
              {profile?.status !== 'approved' && (
                <button className="btn btn-brand btn-sm" disabled={busy} onClick={approve}>
                  Approve
                </button>
              )}
              {profile?.status !== 'rejected' && (
                <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => setRejecting(true)}>
                  Reject
                </button>
              )}
              <Link to={`/profile/${profileUser.id}`} className="btn btn-ghost btn-sm">
                View profile
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* =========================================================================
   Reports queue
   ========================================================================= */

const REPORT_STATUS_TABS = [
  ['pending', 'Pending'],
  ['under review', 'Under review'],
  ['resolved', 'Resolved'],
  ['dismissed', 'Dismissed'],
]

const REASON_LABELS = {
  spam: 'Spam',
  harassment: 'Harassment',
  'hate speech': 'Hate speech',
  'inappropriate content': 'Inappropriate content',
  'copyright violation': 'Copyright violation',
  misinformation: 'Misinformation',
  other: 'Other',
}

function ReportsPanel({ onResolved }) {
  const [tab, setTab] = useState('pending')
  const [reports, setReports] = useState(null)
  const [openId, setOpenId] = useState(null)

  const load = useCallback(async () => {
    setReports(null)
    const res = await reportsApi.list({ status: tab, limit: 50 })
    setReports(res.results)
  }, [tab])

  useEffect(() => {
    load()
  }, [load])

  function handleResolved(reportId, updated) {
    onResolved()
    if (updated.status !== tab) {
      setReports((prev) => prev.filter((r) => r.id !== reportId))
    } else {
      setReports((prev) => prev.map((r) => (r.id === reportId ? updated : r)))
    }
  }

  return (
    <>
      <div className="room-filter-row">
        {REPORT_STATUS_TABS.map(([value, label]) => (
          <button key={value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>
            {label}
          </button>
        ))}
      </div>

      {reports === null ? (
        <Spinner page />
      ) : reports.length === 0 ? (
        <div className="card">
          <EmptyState icon="✅" title="Nothing here" description={`No ${REPORT_STATUS_TABS.find(([v]) => v === tab)?.[1].toLowerCase()} reports right now.`} />
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          {reports.map((report, i) => (
            <div key={report.id} style={i > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
              <ReportRow
                report={report}
                open={openId === report.id}
                onToggle={() => setOpenId((id) => (id === report.id ? null : report.id))}
                onResolved={(updated) => handleResolved(report.id, updated)}
              />
            </div>
          ))}
        </div>
      )}
    </>
  )
}

function ReportRow({ report, open, onToggle, onResolved }) {
  const target = report.post_id ? { type: 'post', id: report.post_id } : { type: 'room', id: report.room_id }

  return (
    <div style={{ padding: 'var(--space-4)' }}>
      <div className="row gap-3" style={{ cursor: 'pointer' }} onClick={onToggle}>
        <Avatar user={report.reporter} size="sm" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
            <Badge tone="accent">{target.type === 'post' ? 'Post' : 'Room'}</Badge>
            <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{REASON_LABELS[report.reason] ?? report.reason}</span>
            <span className="faint" style={{ fontSize: '0.82rem' }}>
              reported by {fullName(report.reporter)} · {relativeTime(report.date_created)}
            </span>
          </div>
          {report.details && <p className="muted truncate" style={{ marginTop: 4, fontSize: '0.86rem' }}>{report.details}</p>}
        </div>
        <Icon.ChevronLeft size={16} style={{ transform: open ? 'rotate(90deg)' : 'rotate(-90deg)', flexShrink: 0 }} />
      </div>

      {open && <ReportDetail report={report} target={target} onResolved={onResolved} />}
    </div>
  )
}

function ReportDetail({ report, target, onResolved }) {
  const [content, setContent] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [notes, setNotes] = useState(report.resolution_notes ?? '')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const c = target.type === 'post' ? await postsApi.get(target.id) : await roomsApi.get(target.id)
        if (!cancelled) setContent(c)
      } catch {
        if (!cancelled) setNotFound(true)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [target.type, target.id])

  async function setStatus(status) {
    setBusy(true)
    try {
      const updated = await reportsApi.update(report.id, { status, resolution_notes: notes.trim() || undefined })
      onResolved(updated)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack gap-3" style={{ marginTop: 'var(--space-3)', paddingLeft: 44 }}>
      <div className="card" style={{ padding: 'var(--space-3) var(--space-4)', background: 'var(--bg-sunken)', border: 'none' }}>
        {notFound ? (
          <span className="faint">This {target.type} no longer exists.</span>
        ) : !content ? (
          <Spinner />
        ) : target.type === 'post' ? (
          <>
            <Link to={`/post/${content.id}`} className="row gap-2" style={{ marginBottom: 6 }}>
              <Avatar user={content.author} size="xs" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{fullName(content.author)}</span>
              <span className="faint" style={{ fontSize: '0.8rem' }}>@{content.author.username}</span>
            </Link>
            <p style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{content.content}</p>
            <Badge>{content.status}</Badge>
          </>
        ) : (
          <>
            <Link to={`/rooms/${content.id}`} style={{ fontWeight: 700, fontSize: '0.9rem' }}>
              {content.name || 'Untitled room'}
            </Link>
            {content.description && <p style={{ fontSize: '0.86rem', marginTop: 4 }}>{content.description}</p>}
            <div style={{ marginTop: 6 }}>
              <Badge>{content.is_suspended ? 'suspended' : content.room_type}</Badge>
            </div>
          </>
        )}
      </div>

      <div className="field">
        <label htmlFor={`notes-${report.id}`}>Resolution notes (optional)</label>
        <textarea
          id={`notes-${report.id}`}
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Why this decision, for the record"
        />
      </div>

      <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
        <button className="btn btn-subtle btn-sm" disabled={busy} onClick={() => setStatus('under review')}>
          Mark under review
        </button>
        <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => setStatus('resolved')}>
          Resolve (keep suspended)
        </button>
        <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setStatus('dismissed')}>
          Dismiss (reinstate)
        </button>
      </div>
    </div>
  )
}
