import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { likesApi, postsApi, commentsApi } from '../api'
import { useAuth } from '../AuthContext'
import { Avatar, Spinner, EmptyState } from '../components/ui'
import { Icon } from '../icons'
import PostCard from '../components/PostCard'
import Composer from '../components/Composer'
import ReportModal from '../components/ReportModal'
import CommentItem, { CommentComposer } from '../components/CommentThread'
import { fullName, relativeTime, formatCount } from '../utils'

export default function PostDetail() {
  const { postId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [post, setPost] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [tab, setTab] = useState(window.location.hash === '#replies' ? 'replies' : 'comments')
  const [liked, setLiked] = useState(false)
  const [likeCount, setLikeCount] = useState(0)
  const [reporting, setReporting] = useState(false)

  const [comments, setComments] = useState(null)
  const [replies, setReplies] = useState(null)

  const load = useCallback(async () => {
    try {
      const p = await postsApi.get(postId)
      setPost(p)
      setLikeCount(p.like_count)
    } catch {
      setNotFound(true)
    }
  }, [postId])

  useEffect(() => {
    setPost(null)
    setNotFound(false)
    setComments(null)
    setReplies(null)
    load()
  }, [load])

  useEffect(() => {
    if (!post) return
    if (tab === 'comments' && comments === null) {
      commentsApi.listForPost(post.id).then((res) => setComments(res.results))
    }
    if (tab === 'replies' && replies === null) {
      postsApi.replies(post.id).then((res) => setReplies(res.results))
    }
  }, [tab, post, comments, replies])

  async function toggleLike() {
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
      if (err.status === 409) setLiked(true)
      if (err.status === 404) setLiked(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm('Delete this post? This cannot be undone.')) return
    await postsApi.remove(post.id)
    navigate('/feed')
  }

  if (notFound) {
    return (
      <div className="shell-content">
        <BackBar />
        <div className="card">
          <EmptyState icon="🔎" title="Post not found" description="It may have been removed or you don't have access." />
        </div>
      </div>
    )
  }

  if (!post) return <Spinner page />

  const isOwner = user?.id === post.author.id

  return (
    <div className="shell-content">
      <BackBar />

      <article className="card thread-post">
        <div className="spread">
          <Link to={`/profile/${post.author.id}`} className="row gap-3">
            <Avatar user={post.author} size="md" />
            <div>
              <div style={{ fontWeight: 700 }}>{fullName(post.author)}</div>
              <div className="faint">@{post.author.username}</div>
            </div>
          </Link>
          {isOwner && (
            <button className="btn-icon" onClick={handleDelete} title="Delete post">
              <Icon.X size={18} />
            </button>
          )}
        </div>

        <p className="post-content" style={{ marginTop: 'var(--space-4)' }}>
          {post.content}
        </p>

        {post.media?.length > 0 && (
          <div className={`post-media-grid${post.media.length === 1 ? ' one' : ''}`}>
            {post.media.map((m) => (
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

        <div className="thread-meta">{new Date(post.date_created).toLocaleString()}</div>

        <div className="thread-stats">
          <span>
            <b>{formatCount(post.reply_count) || 0}</b> Replies
          </span>
          <span>
            <b>{formatCount(post.comment_count) || 0}</b> Comments
          </span>
          <span>
            <b>{formatCount(likeCount) || 0}</b> Likes
          </span>
        </div>

        <div className="thread-actions">
          <span className="post-action" onClick={() => setTab('comments')}>
            <Icon.Comment size={19} />
          </span>
          <span className="post-action" onClick={() => setTab('replies')}>
            <Icon.Repeat size={19} />
          </span>
          <span className={`post-action${liked ? ' liked' : ''}`} onClick={toggleLike}>
            <Icon.Heart size={19} fill={liked ? 'currentColor' : 'none'} />
          </span>
          <span className="post-action" onClick={() => setReporting(true)}>
            <Icon.Flag size={17} />
          </span>
        </div>
      </article>

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="tabs">
          <button className={tab === 'comments' ? 'active' : ''} onClick={() => setTab('comments')}>
            Comments
          </button>
          <button className={tab === 'replies' ? 'active' : ''} onClick={() => setTab('replies')}>
            Replies
          </button>
        </div>

        {tab === 'comments' ? (
          <>
            <CommentComposer
              postId={post.id}
              onCreated={(c) => {
                setComments((prev) => [...(prev ?? []), c])
                setPost((p) => ({ ...p, comment_count: p.comment_count + 1 }))
              }}
            />
            {comments === null ? (
              <Spinner page />
            ) : comments.length === 0 ? (
              <EmptyState icon="💬" title="No comments yet" description="Be the first to say something." />
            ) : (
              comments.map((c) => <CommentItem key={c.id} comment={c} postId={post.id} />)
            )}
          </>
        ) : (
          <>
            <div style={{ borderBottom: '1px solid var(--border)' }}>
              <Composer
                parentPostId={post.id}
                placeholder="Post your reply"
                onCreated={(r) => {
                  setReplies((prev) => [r, ...(prev ?? [])])
                  setPost((p) => ({ ...p, reply_count: p.reply_count + 1 }))
                }}
              />
            </div>
            {replies === null ? (
              <Spinner page />
            ) : replies.length === 0 ? (
              <EmptyState icon="🧵" title="No replies yet" description="Reply to keep this thread going." />
            ) : (
              replies.map((r, i) => (
                <div key={r.id} style={i > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
                  <PostCard post={r} onDeleted={() => setReplies((prev) => prev.filter((x) => x.id !== r.id))} />
                </div>
              ))
            )}
          </>
        )}
      </div>

      {reporting && <ReportModal target={{ type: 'post', id: post.id }} onClose={() => setReporting(false)} />}
    </div>
  )
}

function BackBar() {
  const navigate = useNavigate()
  return (
    <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)} style={{ alignSelf: 'flex-start' }}>
      <Icon.ChevronLeft size={16} /> Back
    </button>
  )
}
