export type FeedbackStatus = 'new' | 'triaged' | 'in_progress' | 'resolved'
export type FeedbackCategory = 'general' | 'bug' | 'feature' | 'usability'
export type AnalysisStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type RequirementStatus = 'draft' | 'confirmed' | 'delivered'

export type Workspace = { id: number; slug: string; name: string }
export type User = { email: string; workspace: Workspace }
export type Session = User & { token: string; expires_at: string }

export type AnalysisResult = {
  suggested_title: string
  problem: string
  known_facts: string[]
  assumptions: string[]
  acceptance_criteria: string[]
  open_questions: string[]
  boundaries: string[]
  related_feedback: { id: number; reason: string; message: string }[]
}

export type Analysis = {
  id: number
  status: AnalysisStatus
  version: number
  result: AnalysisResult | null
  error: string | null
}

export type Feedback = {
  id: number
  message: string
  category: FeedbackCategory
  page_path: string | null
  status: FeedbackStatus
  tags: string
  assignee: string | null
  created_at: string
  requirement_id: number | null
  analysis: Analysis | null
}

export type FeedbackStats = Record<FeedbackStatus | 'total', number>

export type FeedbackFilters = {
  q: string
  status: FeedbackStatus | 'all'
  category: FeedbackCategory | 'all'
  page: number
  pageSize: number
}

export type Page<T> = { items: T[]; total: number; page: number; page_size: number }

export type Task = { id: number; title: string; done: boolean }

export type Requirement = {
  id: number
  title: string
  problem: string
  acceptance_criteria: string
  open_questions: string
  status: RequirementStatus
  source_feedback_ids: number[]
  tasks: Task[]
  created_at: string
  updated_at: string
}

export type RequirementPatch = Partial<Pick<Requirement, 'title' | 'problem' | 'acceptance_criteria' | 'open_questions' | 'status'>>
export type FeedbackPatch = Partial<Pick<Feedback, 'status' | 'tags' | 'assignee'>>

export const FEEDBACK_STATUSES: { value: FeedbackStatus; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'triaged', label: 'Triaged' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
]

export const FEEDBACK_CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: 'bug', label: 'Bug' },
  { value: 'feature', label: 'Feature' },
  { value: 'usability', label: 'Usability' },
  { value: 'general', label: 'General' },
]
