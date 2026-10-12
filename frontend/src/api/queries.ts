import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Feedback, FeedbackFilters, FeedbackPatch, FeedbackStatus, Requirement, RequirementPatch } from '../types'
import { feedbackApi, requirementApi } from './endpoints'

export const keys = {
  feedback: ['feedback'] as const,
  feedbackList: (filters: FeedbackFilters) => ['feedback', 'list', filters] as const,
  feedbackStats: ['feedback', 'stats'] as const,
  feedbackDetail: (id: number) => ['feedback', 'detail', id] as const,
  requirements: ['requirements'] as const,
}

const isPending = (feedback?: Feedback) => feedback?.analysis?.status === 'queued' || feedback?.analysis?.status === 'running'

export function useFeedbackList(filters: FeedbackFilters) {
  return useQuery({
    queryKey: keys.feedbackList(filters),
    queryFn: ({ signal }) => feedbackApi.list(filters, signal),
    placeholderData: keepPreviousData,
  })
}

export function useFeedbackStats() {
  return useQuery({ queryKey: keys.feedbackStats, queryFn: feedbackApi.stats })
}

/** Polls while an analysis is queued or running, then stops. */
export function useFeedback(id: number | null) {
  return useQuery({
    queryKey: keys.feedbackDetail(id ?? 0),
    queryFn: () => feedbackApi.get(id!),
    enabled: id !== null,
    refetchInterval: query => (isPending(query.state.data) ? 1000 : false),
  })
}

export function useRequirements() {
  return useQuery({ queryKey: keys.requirements, queryFn: requirementApi.list })
}

const isFeedback = (value: unknown): value is Feedback => !!value && typeof value === 'object' && 'message' in value

function useFeedbackMutation<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (result: TResult) => {
      if (isFeedback(result)) client.setQueryData(keys.feedbackDetail(result.id), result)
      return client.invalidateQueries({ queryKey: keys.feedback })
    },
  })
}

export const useUpdateFeedback = () =>
  useFeedbackMutation(({ id, patch }: { id: number; patch: FeedbackPatch }) => feedbackApi.update(id, patch))

export const useBulkStatus = () =>
  useFeedbackMutation(({ ids, status }: { ids: number[]; status: FeedbackStatus }) => feedbackApi.bulkStatus(ids, status))

export const useStartAnalysis = () =>
  useFeedbackMutation(({ id, retry }: { id: number; retry: boolean }) => (retry ? feedbackApi.retryAnalysis(id) : feedbackApi.analyze(id)))

export function useCreateRequirement() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (feedbackId: number) => feedbackApi.createRequirement(feedbackId),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: keys.requirements }),
      client.invalidateQueries({ queryKey: keys.feedback }),
    ]),
  })
}

function useRequirementMutation<TArgs>(fn: (args: TArgs) => Promise<Requirement>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: updated => {
      client.setQueryData<Requirement[]>(keys.requirements, current => current?.map(r => (r.id === updated.id ? updated : r)))
      // Delivering a requirement resolves its source feedback.
      if (updated.status === 'delivered') void client.invalidateQueries({ queryKey: keys.feedback })
    },
  })
}

export const useUpdateRequirement = () =>
  useRequirementMutation(({ id, patch }: { id: number; patch: RequirementPatch }) => requirementApi.update(id, patch))
export const useAddTask = () => useRequirementMutation(({ id, title }: { id: number; title: string }) => requirementApi.addTask(id, title))
export const useUpdateTask = () =>
  useRequirementMutation(({ id, taskId, done }: { id: number; taskId: number; done: boolean }) => requirementApi.updateTask(id, taskId, { done }))
export const useDeleteTask = () =>
  useRequirementMutation(({ id, taskId }: { id: number; taskId: number }) => requirementApi.deleteTask(id, taskId))
