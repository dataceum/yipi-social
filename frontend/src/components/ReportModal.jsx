import { useState } from 'react'
import { reportsApi } from '../api'
import { Modal } from './ui'

const REASONS = [
  ['spam', 'Spam'],
  ['harassment', 'Harassment'],
  ['hate speech', 'Hate speech'],
  ['inappropriate content', 'Inappropriate content'],
  ['copyright violation', 'Copyright violation'],
  ['misinformation', 'Misinformation'],
  ['other', 'Other'],
]

export default function ReportModal({ target, onClose }) {
  const [reason, setReason] = useState('spam')
  const [details, setDetails] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = { reason, details: details.trim() || undefined }
      if (target.type === 'post') {
        await reportsApi.reportPost(target.id, payload)
      } else {
        await reportsApi.reportRoom(target.id, payload)
      }
      setDone(true)
    } catch (err) {
      setError(err.detail || 'Could not submit this report.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={`Report this ${target.type}`} onClose={onClose}>
      {done ? (
        <>
          <p className="muted">
            Thanks — this has been flagged for review, and moderators will take a look.
          </p>
          <button className="btn btn-primary btn-block" onClick={onClose}>
            Done
          </button>
        </>
      ) : (
        <form className="stack gap-4" onSubmit={submit}>
          <div className="field">
            <label htmlFor="reason">Reason</label>
            <select id="reason" value={reason} onChange={(e) => setReason(e.target.value)}>
              {REASONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="details">Details (optional)</label>
            <textarea
              id="details"
              rows={3}
              maxLength={1000}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              placeholder="Anything moderators should know?"
            />
          </div>
          {error && <div className="form-alert">{error}</div>}
          <button type="submit" className="btn btn-danger btn-block" disabled={busy}>
            {busy ? 'Submitting…' : 'Submit report'}
          </button>
        </form>
      )}
    </Modal>
  )
}
