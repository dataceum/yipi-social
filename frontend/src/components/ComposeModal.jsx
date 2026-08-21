import { useNavigate } from 'react-router-dom'
import { Modal } from './ui'
import Composer from './Composer'

export default function ComposeModal({ onClose }) {
  const navigate = useNavigate()

  return (
    <Modal title="New post" onClose={onClose}>
      <div className="card" style={{ boxShadow: 'none' }}>
        <Composer
          autoFocus
          onCreated={(post) => {
            onClose()
            navigate(`/post/${post.id}`)
          }}
        />
      </div>
    </Modal>
  )
}
