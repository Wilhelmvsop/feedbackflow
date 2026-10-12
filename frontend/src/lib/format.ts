export const initials = (name: string) =>
  name
    .split(/[ .@_-]/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('')

export const feedbackRef = (id: number) => `FB-${String(id).padStart(3, '0')}`
export const requirementRef = (id: number) => `REQ-${String(id).padStart(3, '0')}`
export const statusLabel = (status: string) => status.replace(/_/g, ' ')

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

export function timeAgo(date: string, now: number = Date.now()): string {
  const elapsed = Math.max(0, now - new Date(date).getTime())
  if (elapsed < MINUTE) return 'Just now'
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} min ago`
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)} h ago`
  const days = Math.floor(elapsed / DAY)
  return days === 1 ? 'Yesterday' : `${days} days ago`
}

export const errorMessage = (error: unknown) => (error instanceof Error ? error.message : 'Something went wrong')
