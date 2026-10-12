import { useEffect, useRef, useState } from 'react'
import { ArrowDownUp, ArrowLeft, ArrowRight, ChevronDown, Command, Filter, Inbox, Layers2, MessageSquare, Plus, Search, Sparkles, Tag } from 'lucide-react'
import { useBulkStatus, useFeedbackList, useFeedbackStats, useUpdateFeedback } from '../api/queries'
import { useToast } from '../lib/toast'
import { errorMessage, feedbackRef, initials, statusLabel, timeAgo } from '../lib/format'
import { useDebounced } from '../lib/useDebounced'
import { FEEDBACK_CATEGORIES, FEEDBACK_STATUSES, type FeedbackCategory, type FeedbackFilters, type FeedbackStatus } from '../types'

const PAGE_SIZE = 20

type Props = { selectedId: number | null; currentUser: string; onSelect: (id: number) => void; onOpenWidgetSetup: () => void }

export function FeedbackInbox({ selectedId, currentUser, onSelect, onOpenWidgetSetup }: Props) {
  const notify = useToast()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<FeedbackFilters['status']>('all')
  const [category, setCategory] = useState<FeedbackFilters['category']>('all')
  const [page, setPage] = useState(1)
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const searchRef = useRef<HTMLInputElement>(null)
  const q = useDebounced(query)

  const filters: FeedbackFilters = { q, status, category, page, pageSize: PAGE_SIZE }
  const list = useFeedbackList(filters)
  const stats = useFeedbackStats()
  const updateFeedback = useUpdateFeedback()
  const bulkStatus = useBulkStatus()

  // Any filter change starts over on page 1 with a clean selection.
  useEffect(() => { setPage(1); setChecked(new Set()) }, [q, status, category])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => { if (list.error) notify(errorMessage(list.error)) }, [list.error, notify])

  const items = list.data?.items ?? []
  const total = list.data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const allChecked = items.length > 0 && items.every(item => checked.has(item.id))
  const filtered = q.trim() !== '' || status !== 'all' || category !== 'all'

  const toggle = (id: number) => setChecked(current => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  const toggleAll = () => setChecked(allChecked ? new Set() : new Set(items.map(item => item.id)))
  const clearFilters = () => { setQuery(''); setStatus('all'); setCategory('all') }

  const applyBulk = (next: FeedbackStatus) => bulkStatus.mutate({ ids: [...checked], status: next }, {
    onSuccess: ({ updated }) => { notify(`Updated ${updated} feedback ${updated === 1 ? 'item' : 'items'}.`); setChecked(new Set()) },
    onError: e => notify(errorMessage(e)),
  })

  const assignToMe = (id: number) => updateFeedback.mutate({ id, patch: { assignee: currentUser } }, { onError: e => notify(errorMessage(e)) })

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR PRODUCT SIGNALS</p>
          <h1>Feedback inbox <span className="heading-count">{stats.data?.total ?? '–'}</span></h1>
          <p className="muted">Every rough edge is a chance to make something better.</p>
        </div>
        <button className="secondary" onClick={onOpenWidgetSetup}><Plus size={16} /> Widget setup</button>
      </div>

      <div className="stat-row">
        <div className="stat-card"><span className="stat-icon green"><MessageSquare size={16} /></span><span className="stat-label">TOTAL FEEDBACK</span><strong>{stats.data?.total ?? '–'}</strong><small>Across all categories</small></div>
        <div className="stat-card"><span className="stat-icon lilac"><Layers2 size={16} /></span><span className="stat-label">IN FLIGHT</span><strong>{stats.data ? stats.data.triaged + stats.data.in_progress : '–'}</strong><small>Triaged or in progress</small></div>
        <div className="stat-card"><span className="stat-icon amber"><Sparkles size={16} /></span><span className="stat-label">NEEDS TRIAGE</span><strong>{stats.data?.new ?? '–'}</strong><small>Fresh from your users</small></div>
        <div className="stat-card stat-note"><div className="note-icon"><Sparkles size={16} /></div><div><strong>A little clarity goes a long way.</strong><p>Turn one feedback into a requirement draft with a little help from AI.</p></div></div>
      </div>

      <section className="feedback-panel">
        <div className="panel-heading">
          <div><h2>All feedback <span>{total}</span></h2><p>Review, organize, and turn signals into action.</p></div>
          {checked.size > 0 ? (
            <div className="bulk-bar">
              <span>{checked.size} selected</span>
              <select aria-label="Set status for selected feedback" value="" disabled={bulkStatus.isPending} onChange={e => applyBulk(e.target.value as FeedbackStatus)}>
                <option value="" disabled>Set status…</option>
                {FEEDBACK_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <button className="text-button" onClick={() => setChecked(new Set())}>Clear</button>
            </div>
          ) : (
            <button className="icon-button" onClick={() => { void list.refetch(); void stats.refetch() }} title="Refresh" aria-label="Refresh"><ArrowDownUp size={16} /></button>
          )}
        </div>

        <div className="toolbar">
          <div className="search-box"><Search size={16} /><input ref={searchRef} aria-label="Search feedback" placeholder="Search feedback…" value={query} onChange={e => setQuery(e.target.value)} /><kbd><Command size={10} /> K</kbd></div>
          <div className="filters">
            <label><Filter size={14} /><select aria-label="Filter by status" value={status} onChange={e => setStatus(e.target.value as FeedbackStatus | 'all')}><option value="all">All status</option>{FEEDBACK_STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}</select><ChevronDown size={13} /></label>
            <label><Tag size={14} /><select aria-label="Filter by category" value={category} onChange={e => setCategory(e.target.value as FeedbackCategory | 'all')}><option value="all">All categories</option>{FEEDBACK_CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}</select><ChevronDown size={13} /></label>
          </div>
        </div>

        <div className="table-scroll" aria-busy={list.isFetching}>
          <table>
            <thead><tr><th><input type="checkbox" aria-label="Select all on this page" checked={allChecked} onChange={toggleAll} /></th><th>FEEDBACK</th><th>CATEGORY</th><th>STATUS</th><th>ASSIGNEE</th><th>RECEIVED</th><th /></tr></thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} className={selectedId === item.id ? 'selected-row' : ''} onClick={() => onSelect(item.id)}>
                  <td><input type="checkbox" aria-label={`Select ${feedbackRef(item.id)}`} checked={checked.has(item.id)} onClick={e => e.stopPropagation()} onChange={() => toggle(item.id)} /></td>
                  <td><div className="feedback-cell"><strong>{item.message}</strong><small><span>{feedbackRef(item.id)}</span>{item.page_path && <><span className="dot">·</span><span>{item.page_path}</span></>}</small></div></td>
                  <td><span className={`category category-${item.category}`}><i />{item.category}</span></td>
                  <td><span className={`status status-${item.status}`}><i />{statusLabel(item.status)}</span></td>
                  <td>{item.assignee
                    ? <span className="assignee"><span className="assignee-avatar">{initials(item.assignee)}</span>{item.assignee}</span>
                    : <button className="assign-button" onClick={e => { e.stopPropagation(); assignToMe(item.id) }}><Plus size={13} /> Assign me</button>}</td>
                  <td className="date-cell" title={new Date(item.created_at).toLocaleString()}>{timeAgo(item.created_at)}</td>
                  <td><button className="row-arrow" aria-label={`Open ${feedbackRef(item.id)}`}><ArrowRight size={15} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.isPending && <div className="empty-state"><span className="spinner" /><p>Loading feedback…</p></div>}
          {!list.isPending && items.length === 0 && (
            <div className="empty-state">
              <div className="empty-icon"><Inbox size={22} /></div>
              <strong>{filtered ? 'No feedback matches these filters' : 'No feedback yet'}</strong>
              <p>{filtered ? 'Try changing your search or filters.' : 'Install the widget to start collecting feedback.'}</p>
              {filtered
                ? <button className="text-button" onClick={clearFilters}>Clear filters</button>
                : <button className="text-button" onClick={onOpenWidgetSetup}>Set up the widget</button>}
            </div>
          )}
        </div>

        <div className="table-footer">
          <span>Showing <strong>{items.length}</strong> of <strong>{total}</strong> feedback {total === 1 ? 'item' : 'items'}</span>
          <div>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} aria-label="Previous page"><ArrowLeft size={14} /></button>
            <span>Page {page} of {pageCount}</span>
            <button disabled={page >= pageCount} onClick={() => setPage(p => p + 1)} aria-label="Next page"><ArrowRight size={14} /></button>
          </div>
        </div>
      </section>
    </>
  )
}
