import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { postsApi } from '../api'
import { Avatar } from './ui'
import { Icon } from '../icons'

const MEDIA_TYPES = [
  { type: 'photo', icon: Icon.Image, label: 'Photo URL' },
  { type: 'video', icon: Icon.Video, label: 'Video URL' },
  { type: 'audio', icon: Icon.Mic, label: 'Audio URL' },
]

export default function Composer({ parentPostId, placeholder = "What's happening?", onCreated, autoFocus = false }) {
  const { user } = useAuth()
  const [content, setContent] = useState('')
  const [media, setMedia] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function addMedia(type) {
    // No file-storage integration on the frontend yet — attaching an
    // already-hosted URL exercises the same PostCreate.media contract a
    // real upload flow would eventually POST to.
    const url = window.prompt(`Paste a ${type} URL to attach:`)
    if (!url) return
    setMedia((m) => [...m, { media_url: url, media_type: type }])
  }

  function removeMedia(idx) {
    setMedia((m) => m.filter((_, i) => i !== idx))
  }

  async function submit(e) {
    e.preventDefault()
    if (!content.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const post = await postsApi.create({
        content: content.trim(),
        media,
        parent_post_id: parentPostId ?? null,
      })
      setContent('')
      setMedia([])
      onCreated?.(post)
    } catch (err) {
      setError(err.detail || 'Could not post. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <Avatar user={user} size="md" />
      <div className="composer-body">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={placeholder}
          maxLength={2000}
          rows={parentPostId ? 2 : 3}
          autoFocus={autoFocus}
        />
        {media.length > 0 && (
          <div className="composer-media-row">
            {media.map((m, i) => (
              <span className="composer-media-chip" key={i}>
                <span className="thumb">{m.media_type === 'photo' ? '🖼️' : m.media_type === 'video' ? '🎬' : '🎧'}</span>
                <span className="truncate" style={{ maxWidth: 120 }}>{m.media_url}</span>
                <button type="button" className="btn-icon" style={{ padding: 2 }} onClick={() => removeMedia(i)}>
                  <Icon.X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        {error && <div className="form-alert">{error}</div>}
        <div className="composer-foot">
          <div className="row gap-2">
            {MEDIA_TYPES.map((m) => (
              <button
                key={m.type}
                type="button"
                className="btn-icon"
                title={m.label}
                onClick={() => addMedia(m.type)}
              >
                <m.icon size={19} />
              </button>
            ))}
          </div>
          <button type="submit" className="btn btn-brand btn-sm" disabled={!content.trim() || busy}>
            {busy ? 'Posting…' : parentPostId ? 'Reply' : 'Post'}
          </button>
        </div>
      </div>
    </form>
  )
}
