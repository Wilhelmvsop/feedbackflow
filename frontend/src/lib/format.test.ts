import { feedbackRef, initials, statusLabel, timeAgo } from './format'

describe('format helpers', () => {
  it('builds initials from names and emails', () => {
    expect(initials('Acme Product Team')).toBe('AP')
    expect(initials('sam.lee@example.com')).toBe('SL')
  })

  it('pads reference ids', () => {
    expect(feedbackRef(7)).toBe('FB-007')
    expect(statusLabel('in_progress')).toBe('in progress')
  })

  it('describes elapsed time', () => {
    const now = Date.parse('2026-01-10T12:00:00Z')
    expect(timeAgo('2026-01-10T11:59:30Z', now)).toBe('Just now')
    expect(timeAgo('2026-01-10T11:15:00Z', now)).toBe('45 min ago')
    expect(timeAgo('2026-01-10T07:00:00Z', now)).toBe('5 h ago')
    expect(timeAgo('2026-01-09T10:00:00Z', now)).toBe('Yesterday')
    expect(timeAgo('2026-01-01T12:00:00Z', now)).toBe('9 days ago')
  })
})
