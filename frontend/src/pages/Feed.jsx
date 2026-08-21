import { useCallback, useEffect, useState } from 'react'
import { postsApi } from '../api'
import Composer from '../components/Composer'
import PostCard from '../components/PostCard'
import { Spinner, EmptyState } from '../components/ui'

const PAGE_SIZE = 20

export default function Feed() {
  const [posts, setPosts] = useState(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)

  const loadFirstPage = useCallback(async () => {
    const res = await postsApi.list({ page: 1, limit: PAGE_SIZE })
    setPosts(res.results)
    setTotal(res.total_count)
    setPage(1)
  }, [])

  useEffect(() => {
    loadFirstPage()
  }, [loadFirstPage])

  async function loadMore() {
    setLoadingMore(true)
    const nextPage = page + 1
    const res = await postsApi.list({ page: nextPage, limit: PAGE_SIZE })
    setPosts((p) => [...p, ...res.results])
    setPage(nextPage)
    setLoadingMore(false)
  }

  function handleCreated(post) {
    setPosts((p) => (p ? [post, ...p] : [post]))
    setTotal((t) => t + 1)
  }

  function handleDeleted(id) {
    setPosts((p) => p.filter((post) => post.id !== id))
    setTotal((t) => Math.max(0, t - 1))
  }

  const hasMore = posts && posts.length < total

  return (
    <div className="shell-content">
      <div className="page-header">
        <h1>Home</h1>
      </div>

      <div className="card">
        <Composer onCreated={handleCreated} />
      </div>

      {posts === null ? (
        <Spinner page />
      ) : posts.length === 0 ? (
        <div className="card">
          <EmptyState
            icon="🌱"
            title="Your feed is empty"
            description="Follow the crowd or just say the first thing — someone will reply."
          />
        </div>
      ) : (
        <>
          <div className="card stack" style={{ overflow: 'hidden' }}>
            {posts.map((post, i) => (
              <div key={post.id} style={i > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
                <PostCard post={post} onDeleted={handleDeleted} />
              </div>
            ))}
          </div>
          {hasMore && (
            <button className="btn btn-ghost btn-block" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </>
      )}
    </div>
  )
}
