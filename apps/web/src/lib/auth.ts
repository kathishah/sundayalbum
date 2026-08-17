import { TOKEN_KEY, USER_HASH_KEY } from '@/lib/constants'

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_HASH_KEY)
}

export function getUserHash(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(USER_HASH_KEY)
}

export function setUserHash(hash: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(USER_HASH_KEY, hash)
}

export function isAuthenticated(): boolean {
  return getToken() !== null
}
