import { useState } from 'react'
import { Link } from 'react-router-dom'
import { commentsApi, likesApi } from '../api'
import { Avatar } from './ui'
import { Icon } from '../icons'
import { fullName, relativeTime } from '../utils'

export function CommentComposer({ postId, parentCommentId, onCreated, onCancel, autoFocus }) {
  const [content, setContent] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!content.trim() || busy) return
    setBusy(true)
    try {
      const comment = await commentsApi.create(postId, {
        content: content.trim(),
        parent_comment_id: parentCommentId ?? null,
      })
      setContent('')
      onCreated?.(comment)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="reply-box" onSubmit={submit}>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={parentCommentId ? 'Write a reply…' : 'Add a comment…'}
        maxLength={1000}
        autoFocus={autoFocus}
      />
      <div className="stack gap-2">
        <button type="submit" className="btn btn-brand btn-sm" disabled={!content.trim() || busy}>
          <Icon.Send size={14} />
        </button>
        {onCancel && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>
            <Icon.X size={14} />
          </button>
        )}
      </div>
    </form>
  )
}

export default function CommentItem({ comment, postId, depth = 0 }) {
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(comment.like_count)
  const [replying, setReplying] = useState(false)
  const [showReplies, setShowReplies] = useState(false)
  const [replies, setReplies] = useState(null)
  const [loadingReplies, setLoadingReplies] = useState(false)

  async function toggleLike() {
    try {
      if (liked) {
        await likesApi.unlikeComment(comment.id)
        setLiked(false)
        setLikeCount((c) => Math.max(0, c - 1))
      } else {
        await likesApi.likeComment(comment.id)
        setLiked(true)
        setLikeCount((c) => c + 1)
      }
    } catch (err) {
      if (err.status === 409) setLiked(true)
      if (err.status === 404) setLiked(false)
    }
  }

  async function loadReplies() {
    if (showReplies) {
      setShowReplies(false)
      return
    }
    setShowReplies(true)
    if (replies === null) {
      setLoadingReplies(true)
      const res = await commentsApi.replies(comment.id)
      setReplies(res.results)
      setLoadingReplies(false)
    }
  }

  return (
    <div className="comment" style={{ marginLeft: depth > 0 ? 28 : 0 }}>
      <Link to={`/profile/${comment.author.id}`}>
        <Avatar user={comment.author} size="sm" />
      </Link>
      <div className="comment-main">
        <div className="post-head truncate">
          <Link to={`/profile/${comment.author.id}`} className="name">
            {fullName(comment.author)}
          </Link>
          <span className="handle">@{comment.author.username}</span>
          <span className="dot">·</span>
          <span className="time">{relativeTime(comment.date_created)}</span>
        </div>
        <p className="comment-body">{comment.content}</p>
        <div className="comment-actions">
          <span className={`post-action${liked ? ' liked' : ''}`} onClick={toggleLike}>
            <Icon.Heart size={15} fill={liked ? 'currentColor' : 'none'} /> {likeCount || ''}
          </span>
          <span className="post-action" onClick={() => setReplying((v) => !v)}>
            <Icon.Comment size={15} /> Reply
          </span>
          {comment.reply_count > 0 && (
            <span className="post-action" onClick={loadReplies}>
              {showReplies ? 'Hide' : `${comment.reply_count} ${comment.reply_count === 1 ? 'reply' : 'replies'}`}
            </span>
          )}
        </div>

        {replying && (
          <CommentComposer
            postId={postId}
            parentCommentId={comment.id}
            autoFocus
            onCancel={() => setReplying(false)}
            onCreated={() => {
              setReplying(false)
              setReplies(null)
              setShowReplies(true)
              loadReplies()
            }}
          />
        )}

        {showReplies && (
          <div className="stack" style={{ marginTop: 8 }}>
            {loadingReplies && <span className="faint" style={{ fontSize: '0.82rem' }}>Loading replies…</span>}
            {replies?.map((r) => (
              <CommentItem key={r.id} comment={r} postId={postId} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
