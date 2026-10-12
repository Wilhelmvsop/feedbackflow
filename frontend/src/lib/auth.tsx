import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { setAuthToken, setUnauthorizedHandler } from '../api/client'
import { authApi } from '../api/endpoints'
import type { Session } from '../types'

const STORAGE_KEY = 'ff-session'

type AuthContextValue = {
  session: Session | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredSession(): Session | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const session = JSON.parse(raw) as Session
    if (!session.token || new Date(session.expires_at).getTime() <= Date.now()) return null
    return session
  } catch {
    return null
  }
}

function storeSession(session: Session | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable (private mode); the session just won't survive a reload */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<Session | null>(() => {
    const stored = readStoredSession()
    setAuthToken(stored?.token ?? null)
    return stored
  })

  const clear = useCallback(() => {
    setAuthToken(null)
    storeSession(null)
    setSession(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    return () => setUnauthorizedHandler(null)
  }, [clear])

  const signIn = useCallback(async (email: string, password: string) => {
    const next = await authApi.login(email, password)
    setAuthToken(next.token)
    storeSession(next)
    setSession(next)
  }, [])

  const signOut = useCallback(async () => {
    await authApi.logout().catch(() => undefined)
    clear()
  }, [clear])

  const value = useMemo(() => ({ session, signIn, signOut }), [session, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
