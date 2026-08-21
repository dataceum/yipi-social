import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, usersApi, tokenStore, setUnauthorizedHandler } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 'loading' = still resolving the initial session on first load.
  const [status, setStatus] = useState('loading')

  const loadMe = useCallback(async () => {
    try {
      const me = await usersApi.me()
      setUser(me)
      setStatus('authenticated')
      return me
    } catch {
      tokenStore.clear()
      setUser(null)
      setStatus('anonymous')
      return null
    }
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      setStatus('anonymous')
    })
    if (tokenStore.access) {
      loadMe()
    } else {
      setStatus('anonymous')
    }
  }, [loadMe])

  const login = useCallback(
    async (username, password) => {
      const res = await authApi.login({ username, password })
      tokenStore.set(res.access_token, res.refresh_token)
      const me = await loadMe()
      return { ...res, me }
    },
    [loadMe]
  )

  const signup = useCallback(async (payload) => {
    return authApi.signup(payload)
  }, [])

  const logout = useCallback(async () => {
    const refresh = tokenStore.refresh
    tokenStore.clear()
    setUser(null)
    setStatus('anonymous')
    if (refresh) {
      try {
        await authApi.logout(refresh)
      } catch {
        // Already logged out client-side regardless of server response.
      }
    }
  }, [])

  const refreshUser = useCallback(() => loadMe(), [loadMe])

  const value = { user, status, login, signup, logout, refreshUser }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
