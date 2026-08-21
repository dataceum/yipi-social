import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Spinner } from './components/ui'
import Shell from './components/Shell'
import { homeRouteFor, isReviewer } from './utils'

import Landing from './pages/Landing'
import { Login, Signup } from './pages/Auth'
import Feed from './pages/Feed'
import PostDetail from './pages/PostDetail'
import Profile from './pages/Profile'
import Settings from './pages/Settings'
import Search from './pages/Search'
import Rooms from './pages/Rooms'
import RoomDetail from './pages/RoomDetail'
import Moderation from './pages/Moderation'
import NotFound from './pages/NotFound'

function RequireAuth({ children }) {
  const { status } = useAuth()
  if (status === 'loading') return <Spinner page />
  if (status === 'anonymous') return <Navigate to="/login" replace />
  return children
}

// Admins/moderators get the moderation queue; everyone else is bounced to
// the feed if they try to hit /moderation directly.
function RequireReviewer({ children }) {
  const { status, user } = useAuth()
  if (status === 'loading') return <Spinner page />
  if (status === 'anonymous') return <Navigate to="/login" replace />
  if (!isReviewer(user)) return <Navigate to="/feed" replace />
  return children
}

function RedirectIfAuthed({ children }) {
  const { status, user } = useAuth()
  if (status === 'authenticated') return <Navigate to={homeRouteFor(user)} replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<RedirectIfAuthed><Login /></RedirectIfAuthed>} />
      <Route path="/signup" element={<RedirectIfAuthed><Signup /></RedirectIfAuthed>} />

      <Route
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route path="/feed" element={<Feed />} />
        <Route path="/post/:postId" element={<PostDetail />} />
        <Route path="/profile/:userId" element={<Profile />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/search" element={<Search />} />
        <Route path="/rooms" element={<Rooms />} />
        <Route path="/rooms/:roomId" element={<RoomDetail />} />
        <Route
          path="/moderation"
          element={
            <RequireReviewer>
              <Moderation />
            </RequireReviewer>
          }
        />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
