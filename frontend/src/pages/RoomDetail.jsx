import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { roomsApi } from '../api'
import { useAuth } from '../AuthContext'
import { Avatar, Spinner, EmptyState, Badge } from '../components/ui'
import { Icon } from '../icons'
import ReportModal from '../components/ReportModal'
import { fullName, relativeTime } from '../utils'

const POLL_MS = 4000

export default function RoomDetail() {
  const { roomId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [room, setRoom] = useState(null)
  const [members, setMembers] = useState(null)
  const [messages, setMessages] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [draft, setDraft] = useState('')
  const [reporting, setReporting] = useState(false)
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef(null)

  const loadRoom = useCallback(async () => {
    try {
      const r = await roomsApi.get(roomId)
      setRoom(r)
      const m = await roomsApi.members(roomId).catch(() => null)
      if (m) setMembers(m.results)
    } catch {
      setNotFound(true)
    }
  }, [roomId])

  useEffect(() => {
    setRoom(null)
    setMembers(null)
    setMessages(null)
    setNotFound(false)
    loadRoom()
  }, [loadRoom])

  const isMember = members?.some((m) => m.user.id === user?.id)
  const isOwner = room?.owner_id === user?.id
  const canSeeMessages = isMember || isOwner

  const loadMessages = useCallback(async () => {
    if (!canSeeMessages) return
    try {
      const res = await roomsApi.messages(roomId)
      setMessages(res.results)
    } catch {
      // Access can change (e.g. suspended room) — just stop trying silently.
    }
  }, [roomId, canSeeMessages])

  useEffect(() => {
    if (!canSeeMessages) return
    loadMessages()
    const id = setInterval(loadMessages, POLL_MS)
    return () => clearInterval(id)
  }, [canSeeMessages, loadMessages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  async function join() {
    setBusy(true)
    try {
      await roomsApi.join(roomId)
      await loadRoom()
    } finally {
      setBusy(false)
    }
  }

  async function leave() {
    if (!window.confirm('Leave this room?')) return
    await roomsApi.leave(roomId, user.id)
    navigate('/rooms')
  }

  async function deleteRoom() {
    if (!window.confirm('Delete this room permanently?')) return
    await roomsApi.remove(roomId)
    navigate('/rooms')
  }

  async function setStatus(status) {
    setBusy(true)
    try {
      const updated = await roomsApi.update(roomId, { status })
      setRoom(updated)
    } finally {
      setBusy(false)
    }
  }

  async function sendMessage(e) {
    e.preventDefault()
    if (!draft.trim()) return
    const content = draft.trim()
    setDraft('')
    const msg = await roomsApi.sendMessage(roomId, content)
    setMessages((prev) => [...(prev ?? []), msg])
  }

  if (notFound) {
    return (
      <div className="shell-content">
        <div className="card">
          <EmptyState icon="🔒" title="This room isn't available" description="It may be private, suspended, or gone." />
        </div>
      </div>
    )
  }

  if (!room) return <Spinner page />

  const isChat = room.room_type === 'chat'
  const icon = isChat ? '💬' : room.room_type === 'live_video' ? '🎬' : '🎙️'

  return (
    <div className="shell-content wide">
      <button className="btn btn-ghost btn-sm" onClick={() => navigate('/rooms')} style={{ alignSelf: 'flex-start' }}>
        <Icon.ChevronLeft size={16} /> Rooms
      </button>

      <div className="card room-detail-head">
        <div className="room-detail-title-row">
          <div className="row gap-3">
            <div className="room-thumb" style={{ width: 48, height: 48, fontSize: '1.2rem' }}>
              {icon}
            </div>
            <div>
              <h1>{room.name || (isChat ? 'Untitled chat' : 'Untitled Space')}</h1>
              <div className="row gap-2" style={{ marginTop: 4 }}>
                {room.status === 'live' && <Badge tone="live">Live</Badge>}
                {room.status === 'scheduled' && <Badge>Scheduled</Badge>}
                {room.status === 'ended' && <Badge>Ended</Badge>}
                {room.is_suspended && <Badge tone="live">Suspended</Badge>}
              </div>
            </div>
          </div>
          <button className="btn-icon" onClick={() => setReporting(true)} title="Report room">
            <Icon.Flag size={17} />
          </button>
        </div>

        {room.description && <p className="muted">{room.description}</p>}

        <div className="room-members-strip">
          <div className="stack-avatars">
            {members?.slice(0, 5).map((m) => (
              <Avatar key={m.id} user={m.user} size="sm" />
            ))}
          </div>
          <span className="faint">{room.member_count} member{room.member_count === 1 ? '' : 's'}</span>
        </div>

        <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
          {!isMember && !isOwner && !isChat && (
            <button className="btn btn-brand btn-sm" onClick={join} disabled={busy}>
              Join
            </button>
          )}
          {(isMember || isOwner) && (
            <button className="btn btn-ghost btn-sm" onClick={leave}>
              Leave
            </button>
          )}
          {isOwner && !isChat && room.status === 'scheduled' && (
            <button className="btn btn-subtle btn-sm" onClick={() => setStatus('live')} disabled={busy}>
              Go live
            </button>
          )}
          {isOwner && !isChat && room.status === 'live' && (
            <button className="btn btn-danger btn-sm" onClick={() => setStatus('ended')} disabled={busy}>
              End Space
            </button>
          )}
          {isOwner && (
            <button className="btn btn-danger btn-sm" onClick={deleteRoom}>
              Delete room
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ overflow: 'hidden' }}>
        {!canSeeMessages ? (
          <EmptyState
            icon="🔒"
            title={isChat ? 'Invite-only' : 'Join to see the conversation'}
            description={isChat ? 'This chat thread is invite-only.' : 'Join this room to view and send messages.'}
          />
        ) : messages === null ? (
          <Spinner page />
        ) : (
          <>
            <div className="room-messages">
              {messages.length === 0 && (
                <EmptyState icon="👋" title="No messages yet" description="Say hello to get things started." />
              )}
              {messages.map((m) => {
                const mine = m.author.id === user?.id
                return (
                  <div className={`room-message${mine ? ' mine' : ''}`} key={m.id}>
                    <Avatar user={m.author} size="xs" />
                    <div>
                      <div className="bubble">{m.content}</div>
                      <div className="meta">{mine ? 'You' : fullName(m.author)} · {relativeTime(m.date_created)}</div>
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>
            <form className="room-composer" onSubmit={sendMessage}>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Send a message"
                maxLength={2000}
              />
              <button type="submit" className="btn btn-brand btn-sm" disabled={!draft.trim()}>
                <Icon.Send size={15} />
              </button>
            </form>
          </>
        )}
      </div>

      {reporting && <ReportModal target={{ type: 'room', id: room.id }} onClose={() => setReporting(false)} />}
    </div>
  )
}
