import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { postsApi, usersApi } from '../api'
import { useAuth } from '../AuthContext'
import { Avatar, Spinner, EmptyState } from '../components/ui'
import PostCard from '../components/PostCard'
import { Icon } from '../icons'
import { fullName } from '../utils'

export default function Profile() {
  const { userId } = useParams()
  const { user: me } = useAuth()

  const [profileUser, setProfileUser] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [posts, setPosts] = useState(null)
  const [playingBio, setPlayingBio] = useState(false)

  const load = useCallback(async () => {
    setProfileUser(null)
    setPosts(null)
    setNotFound(false)
    try {
      const u = await usersApi.get(userId)
      setProfileUser(u)
      const p = await postsApi.list({ authorId: userId })
      setPosts(p.results)
    } catch {
      setNotFound(true)
    }
  }, [userId])

  useEffect(() => {
    load()
  }, [load])

  if (notFound) {
    return (
      <div className="shell-content">
        <div className="card">
          <EmptyState icon="🔎" title="Profile not found" description="This account may not exist or isn't visible to you." />
        </div>
      </div>
    )
  }

  if (!profileUser) return <Spinner page />

  const isMe = me?.id === profileUser.id
  const bioUrl = profileUser.profile?.bio_recording_url
  const pictureUrl = profileUser.profile?.profile_picture_url

  return (
    <div className="shell-content">
      <div className="card" style={{ padding: 'var(--space-4)' }}>
        <div className="profile-cover" />
        <div className="profile-header">
          <div className="profile-avatar-row">
            <Avatar user={{ ...profileUser, profile: { profile_picture_url: pictureUrl } }} size="xl" />
            {isMe ? (
              <Link to="/settings" className="btn btn-ghost btn-sm">
                Edit profile
              </Link>
            ) : (
              <button className="btn btn-subtle btn-sm">Message</button>
            )}
          </div>
          <div className="profile-name">{fullName(profileUser)}</div>
          <div className="profile-handle">@{profileUser.username}</div>

          {bioUrl && (
            <button className="btn btn-subtle btn-sm" style={{ marginTop: 'var(--space-3)' }} onClick={() => setPlayingBio((v) => !v)}>
              <Icon.Mic size={15} /> {playingBio ? 'Hide' : 'Play'} voice bio
            </button>
          )}
          {playingBio && bioUrl && (
            <audio controls src={bioUrl} style={{ width: '100%', marginTop: 'var(--space-3)' }} />
          )}

          <div className="profile-meta-row">
            <span>
              <b>{posts?.length ?? 0}</b> posts
            </span>
          </div>
        </div>
      </div>

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="tabs">
          <button className="active">Posts</button>
        </div>
        {posts === null ? (
          <Spinner page />
        ) : posts.length === 0 ? (
          <EmptyState icon="📝" title="No posts yet" description={isMe ? 'Share your first post from the Home tab.' : "This user hasn't posted yet."} />
        ) : (
          posts.map((post, i) => (
            <div key={post.id} style={i > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
              <PostCard post={post} onDeleted={() => setPosts((p) => p.filter((x) => x.id !== post.id))} />
            </div>
          ))
        )}
      </div>
    </div>
  )
}
