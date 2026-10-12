import type {
  Feedback, FeedbackFilters, FeedbackPatch, FeedbackStats, FeedbackStatus, Page, Requirement, RequirementPatch, Session, User,
} from '../types'
import { request } from './client'

type AnalysisJob = { analysis_id: number; status: string; version: number }

export const authApi = {
  login: (email: string, password: string) => request<Session>('/auth/login', { method: 'POST', body: { email, password } }),
  me: () => request<User>('/auth/me'),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
}

export const feedbackApi = {
  list: ({ q, status, category, page, pageSize }: FeedbackFilters, signal?: AbortSignal) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (q.trim()) params.set('q', q.trim())
    if (status !== 'all') params.set('status', status)
    if (category !== 'all') params.set('category', category)
    return request<Page<Feedback>>(`/feedback?${params}`, { signal })
  },
  stats: () => request<FeedbackStats>('/feedback/stats'),
  get: (id: number) => request<Feedback>(`/feedback/${id}`),
  update: (id: number, patch: FeedbackPatch) => request<Feedback>(`/feedback/${id}`, { method: 'PATCH', body: patch }),
  bulkStatus: (ids: number[], status: FeedbackStatus) =>
    request<{ updated: number }>('/feedback/bulk', { method: 'POST', body: { ids, status } }),
  analyze: (id: number) => request<AnalysisJob>(`/feedback/${id}/analysis`, { method: 'POST' }),
  retryAnalysis: (id: number) => request<AnalysisJob>(`/feedback/${id}/analysis/retry`, { method: 'POST' }),
  createRequirement: (id: number) => request<Requirement>(`/feedback/${id}/requirement`, { method: 'POST' }),
}

export const requirementApi = {
  list: () => request<Requirement[]>('/requirements'),
  update: (id: number, patch: RequirementPatch) => request<Requirement>(`/requirements/${id}`, { method: 'PATCH', body: patch }),
  addTask: (id: number, title: string) => request<Requirement>(`/requirements/${id}/tasks`, { method: 'POST', body: { title } }),
  updateTask: (id: number, taskId: number, patch: { done?: boolean; title?: string }) =>
    request<Requirement>(`/requirements/${id}/tasks/${taskId}`, { method: 'PATCH', body: patch }),
  deleteTask: (id: number, taskId: number) => request<Requirement>(`/requirements/${id}/tasks/${taskId}`, { method: 'DELETE' }),
}
