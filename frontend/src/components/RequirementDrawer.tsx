import { useState, type FormEvent } from 'react'
import { ArrowRight, Check, CheckCheck, MessageSquare, Plus, Trash2, X } from 'lucide-react'
import { useAddTask, useDeleteTask, useUpdateRequirement, useUpdateTask } from '../api/queries'
import { useToast } from '../lib/toast'
import { errorMessage, requirementRef } from '../lib/format'
import type { Requirement, RequirementPatch } from '../types'
import { useEscape } from './useEscape'

type TextField = 'title' | 'problem' | 'acceptance_criteria' | 'open_questions'

const FIELDS: { key: TextField; label: string; rows?: number; className?: string }[] = [
  { key: 'title', label: 'TITLE', className: 'title-input' },
  { key: 'problem', label: 'PROBLEM STATEMENT', rows: 4 },
  { key: 'acceptance_criteria', label: 'ACCEPTANCE CRITERIA', rows: 5, className: 'criteria-input' },
  { key: 'open_questions', label: 'OPEN QUESTIONS', rows: 3 },
]

export function RequirementDrawer({ requirement, onClose }: { requirement: Requirement; onClose: () => void }) {
  const notify = useToast()
  const update = useUpdateRequirement()
  const addTask = useAddTask()
  const updateTask = useUpdateTask()
  const deleteTask = useDeleteTask()
  const [form, setForm] = useState(() => Object.fromEntries(FIELDS.map(f => [f.key, requirement[f.key]])) as Record<TextField, string>)
  const [taskText, setTaskText] = useState('')
  useEscape(onClose)

  const onError = (e: unknown) => notify(errorMessage(e))
  const save = (patch: RequirementPatch) => update.mutate({ id: requirement.id, patch }, { onError })
  const saveField = (key: TextField) => {
    const value = form[key]
    if (value === requirement[key]) return
    if (key === 'title' && !value.trim()) {
      setForm(current => ({ ...current, title: requirement.title }))
      return notify('A requirement needs a title.')
    }
    save({ [key]: value })
  }
  const submitTask = (event: FormEvent) => {
    event.preventDefault()
    if (!taskText.trim()) return
    addTask.mutate({ id: requirement.id, title: taskText.trim() }, { onSuccess: () => setTaskText(''), onError })
  }

  const done = requirement.tasks.filter(t => t.done).length
  const { status } = requirement

  return (
    <>
      <button className="drawer-scrim" aria-label="Close requirement" onClick={onClose} />
      <aside className="detail-drawer" aria-label="Requirement draft">
        <div className="drawer-top">
          <div><span className="detail-id">REQUIREMENT · {requirementRef(requirement.id)}</span><button className="drawer-close" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
          <h2>Requirement draft</h2>
        </div>
        <div className="drawer-scroll req-editor">
          <div className="detail-status-row">
            <span className={`req-status req-${status}`}>{status}</span>
            <span className="source-note"><MessageSquare size={13} /> Feedback #{requirement.source_feedback_ids.join(', #')}</span>
          </div>
          {FIELDS.map(field => (
            <label className="field-label" key={field.key}>
              {field.label}
              {field.rows
                ? <textarea className={`detail-input ${field.className ?? ''}`} rows={field.rows} value={form[field.key]} onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))} onBlur={() => saveField(field.key)} />
                : <input className={`detail-input ${field.className ?? ''}`} maxLength={200} value={form[field.key]} onChange={e => setForm(f => ({ ...f, [field.key]: e.target.value }))} onBlur={() => saveField(field.key)} />}
            </label>
          ))}
          <div className="detail-divider" />

          <div className="tasks-heading"><div><h3>Development tasks</h3><small>{done} of {requirement.tasks.length} complete</small></div><span className="task-count">{requirement.tasks.length}</span></div>
          <div className="task-list">
            {requirement.tasks.map(task => (
              <div className={`task-row ${task.done ? 'task-done' : ''}`} key={task.id}>
                <label>
                  <input type="checkbox" checked={task.done} onChange={() => updateTask.mutate({ id: requirement.id, taskId: task.id, done: !task.done }, { onError })} />
                  <span>{task.title}</span>
                </label>
                <button className="task-delete" aria-label={`Delete task ${task.title}`} onClick={() => deleteTask.mutate({ id: requirement.id, taskId: task.id }, { onError })}><Trash2 size={13} /></button>
              </div>
            ))}
            {!requirement.tasks.length && <p className="muted">Break this requirement into a few concrete steps.</p>}
          </div>
          <form className="add-task" onSubmit={submitTask}>
            <Plus size={15} />
            <input placeholder="Add a development task…" aria-label="New task" maxLength={200} value={taskText} onChange={e => setTaskText(e.target.value)} />
            <button disabled={!taskText.trim() || addTask.isPending} aria-label="Add task"><ArrowRight size={16} /></button>
          </form>
          <div className="detail-divider" />

          <div className="confirm-card">
            <div className="confirm-icon"><CheckCheck size={17} /></div>
            <div>
              <strong>{status === 'draft' ? 'Ready for a human review?' : status === 'confirmed' ? 'This requirement is confirmed.' : 'Delivered'}</strong>
              <p>{status === 'draft' ? 'Confirm the scope before it enters the team’s plan.' : status === 'confirmed' ? 'Source feedback will resolve after delivery.' : 'Source feedback has been marked resolved.'}</p>
            </div>
          </div>
        </div>
        <div className="drawer-bottom">
          <span><Check size={14} /> Changes saved automatically</span>
          {status === 'draft' && <button className="confirm-button" disabled={update.isPending} onClick={() => save({ status: 'confirmed' })}><Check size={14} /> Confirm requirement</button>}
          {status === 'confirmed' && <button className="confirm-button" disabled={update.isPending} onClick={() => save({ status: 'delivered' })}><CheckCheck size={14} /> Mark delivered</button>}
          {status === 'delivered' && <button onClick={onClose}>Done</button>}
        </div>
      </aside>
    </>
  )
}
