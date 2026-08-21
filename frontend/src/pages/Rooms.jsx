import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { roomsApi } from '../api'
import { Spinner, EmptyState, Badge, Modal } from '../components/ui'
import { Icon } from '../icons'

const FILTERS = [
  { value: undefined, label: 'All' },
  { value: 'live_audio', label: 'Live audio' },
  { value: 'live_video', label: 'Live video' },
  { value: 'chat', label: 'Chats' },
]

export default function Rooms() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState(undefined)
  const [rooms, setRooms] = useState(null)
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setRooms(null)
    const res = await roomsApi.list({ roomType: filter })
    setRooms(res.results)
  }, [filter])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="shell-content wide">
      <div className="page-header">
        <div>
          <h1>Spaces</h1>
          <p>Live rooms and chat threads</p>
        </div>
        <button className="btn btn-brand" onClick={() => setCreating(true)}>
          <Icon.Plus size={16} /> New
        </button>
      </div>

      <div className="room-filter-row">
        {FILTERS.map((f) => (
          <button key={f.label} className={filter === f.value ? 'active' : ''} onClick={() => setFilter(f.value)}>
            {f.label}
          </button>
        ))}
      </div>

      {rooms === null ? (
        <Spinner page />
      ) : rooms.length === 0 ? (
        <div className="card">
          <EmptyState icon="🎙️" title="No rooms yet" description="Start a live Space or open a chat thread." />
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          {rooms.map((room, i) => (
            <div key={room.id} style={i > 0 ? { borderTop: '1px solid var(--border)' } : undefined}>
              <RoomRow room={room} onClick={() => navigate(`/rooms/${room.id}`)} />
            </div>
          ))}
        </div>
      )}

      {creating && (
        <CreateRoomModal
          onClose={() => setCreating(false)}
          onCreated={(room) => {
            setCreating(false)
            navigate(`/rooms/${room.id}`)
          }}
        />
      )}
    </div>
  )
}

function RoomRow({ room, onClick }) {
  const icon = room.room_type === 'chat' ? '💬' : room.room_type === 'live_video' ? '🎬' : '🎙️'
  return (
    <div className="room-card" onClick={onClick} style={{ cursor: 'pointer' }}>
      <div className="room-thumb">{icon}</div>
      <div className="room-info">
        <h3 className="truncate">{room.name || (room.room_type === 'chat' ? 'Untitled chat' : 'Untitled Space')}</h3>
        <p className="truncate">{room.description || `${room.member_count} member${room.member_count === 1 ? '' : 's'}`}</p>
      </div>
      {room.status === 'live' && <Badge tone="live">Live</Badge>}
      {room.status === 'scheduled' && <Badge>Scheduled</Badge>}
    </div>
  )
}

const ROOM_TYPES = [
  ['live_audio', '🎙️ Live audio'],
  ['live_video', '🎬 Live video'],
  ['chat', '💬 Group chat'],
]

function CreateRoomModal({ onClose, onCreated }) {
  const [roomType, setRoomType] = useState('live_audio')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const room = await roomsApi.create({
        room_type: roomType,
        name: name.trim() || null,
        description: description.trim() || null,
        participant_ids: [],
      })
      onCreated(room)
    } catch (err) {
      setError(err.detail || 'Could not create this room.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Start something new" onClose={onClose}>
      <form className="stack gap-4" onSubmit={submit}>
        <div className="field">
          <label>Type</label>
          <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
            {ROOM_TYPES.map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`btn btn-sm ${roomType === value ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setRoomType(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label htmlFor="room_name">Name</label>
          <input id="room_name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Give it a name" />
        </div>
        <div className="field">
          <label htmlFor="room_desc">Description</label>
          <textarea id="room_desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        {error && <div className="form-alert">{error}</div>}
        <button type="submit" className="btn btn-brand btn-block" disabled={busy}>
          {busy ? 'Creating…' : 'Create'}
        </button>
      </form>
    </Modal>
  )
}
