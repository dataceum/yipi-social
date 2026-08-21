import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { likesApi, postsApi } from '../api'
import { Avatar } from './ui'
import { Icon } from '../icons'
import { fullName, relativeTime, formatCount } from '../utils'
import ReportModal from './ReportModal'

/**
 * A post's list-response payload has no "did I like this" flag (see
 * models/post.py — like_count is the only signal). We track "liked"
 * optimistically client-side and reconcile against 409 (already liked) /
 * 404 (not liked) responses from the like endpoints so a stale guess
 * self-corrects on the first click rather than drifting forever.
 */
export default function PostCard({ post, onDeleted }) {
  const navigate = useNavigate()
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(post.like_count)
  const [busyLike, setBusyLike] = useState(false)
  const [reporting, setReporting] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  async function toggleLike(e) {
    e.stopPropagation()
    if (busyLike) return
    setBusyLike(true)
    try {
      if (liked) {
        await likesApi.unlikePost(post.id)
        setLiked(false)
        setLikeCount((c) => Math.max(0, c - 1))
      } else {
        await likesApi.likePost(post.id)
        setLiked(true)
        setLikeCount((c) => c + 1)
      }
    } catch (err) {
      if (err.status === 409) {
        setLiked(true)
      } else if (err.status === 404) {
        setLiked(false)
      }
    } finally {
      setBusyLike(false)
    }
  }

  async function handleDelete(e) {
    e.stopPropagation()
    if (!window.confirm('Delete this post? This cannot be undone.')) return
    await postsApi.remove(post.id)
    onDeleted?.(post.id)
  }

  const media = post.media ?? []

  return (
    <article className="card post-card" onClick={() => navigate(`/post/${post.id}`)}>
      <Avatar user={post.author} size="md" />
      <div className="post-main">
        <div className="spread">
          <div className="post-head truncate">
            <span className="name">{fullName(post.author)}</span>
            <span className="handle">@{post.author.username}</span>
            <span className="dot">·</span>
            <span className="time">{relativeTime(post.date_created)}</span>
          </div>
          <div style={{ position: 'relative' }}>
            <button
              className="btn-icon"
              onClick={(e) => {
                e.stopPropagation()
                setMenuOpen((v) => !v)
              }}
              aria-label="More"
            >
              <Icon.MoreHorizontal size={17} />
            </button>
            {menuOpen && (
              <PostMenu
                onClose={() => setMenuOpen(false)}
                onReport={() => {
                  setMenuOpen(false)
                  setReporting(true)
                }}
                onDelete={handleDelete}
              />
            )}
          </div>
        </div>

        <p className="post-content">{post.content}</p>

        {media.length > 0 && (
          <div className={`post-media-grid${media.length === 1 ? ' one' : ''}`}>
            {media.slice(0, 4).map((m) => (
              <div className="post-media-tile" key={m.id}>
                {m.media_type === 'photo' && '🖼️'}
                {m.media_type === 'video' && '🎬'}
                {m.media_type === 'audio' && '🎧'}
                {m.media_type === 'document' && '📄'}
                <span>{m.media_type}</span>
              </div>
            ))}
          </div>
        )}

        <div className="post-actions">
          <span className="post-action" onClick={(e) => { e.stopPropagation(); navigate(`/post/${post.id}`) }}>
            <Icon.Comment size={17} />
            {formatCount(post.comment_count) || ''}
          </span>
          <span className="post-action" onClick={(e) => { e.stopPropagation(); navigate(`/post/${post.id}#replies`) }}>
            <Icon.Repeat size={17} />
            {formatCount(post.reply_count) || ''}
          </span>
          <span className={`post-action${liked ? ' liked' : ''}`} onClick={toggleLike}>
            <Icon.Heart size={17} fill={liked ? 'currentColor' : 'none'} />
            {formatCount(likeCount) || ''}
          </span>
          <span className="post-action" onClick={(e) => { e.stopPropagation(); setReporting(true) }}>
            <Icon.Flag size={16} />
          </span>
        </div>
      </div>

      {reporting && (
        <div onClick={(e) => e.stopPropagation()}>
          <ReportModal target={{ type: 'post', id: post.id }} onClose={() => setReporting(false)} />
        </div>
      )}
    </article>
  )
}

function PostMenu({ onClose, onReport, onDelete }) {
  return (
    <div
      className="card"
      style={{ position: 'absolute', right: 0, top: '110%', zIndex: 10, minWidth: 160, padding: 6 }}
      onMouseLeave={onClose}
    >
      <button className="btn btn-ghost btn-sm btn-block" style={{ justifyContent: 'flex-start', border: 'none' }} onClick={onReport}>
        <Icon.Flag size={15} /> Report
      </button>
      <button
        className="btn btn-ghost btn-sm btn-block"
        style={{ justifyContent: 'flex-start', border: 'none', color: 'var(--danger)' }}
        onClick={onDelete}
      >
        <Icon.X size={15} /> Delete
      </button>
    </div>
  )
}
