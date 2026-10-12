import { useCallback, useEffect, useState } from 'react'
import { useFeedbackStats, useRequirements } from './api/queries'
import { FeedbackDrawer } from './components/FeedbackDrawer'
import { FeedbackInbox } from './components/FeedbackInbox'
import { LoginPage } from './components/LoginPage'
import { RequirementDrawer } from './components/RequirementDrawer'
import { RequirementsView } from './components/RequirementsView'
import { Sidebar, type View } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { WidgetSetupDialog } from './components/WidgetSetupDialog'
import { useAuth } from './lib/auth'
import type { Session } from './types'

export default function App() {
  const { session } = useAuth()
  return session ? <Workspace session={session} /> : <LoginPage />
}

const viewFromHash = (): View => (window.location.hash === '#/requirements' ? 'requirements' : 'feedback')

function useHashView(): [View, (view: View) => void] {
  const [view, setView] = useState<View>(viewFromHash)
  useEffect(() => {
    const onChange = () => setView(viewFromHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  const navigate = useCallback((next: View) => { window.location.hash = next === 'requirements' ? '#/requirements' : '#/' }, [])
  return [view, navigate]
}

function Workspace({ session }: { session: Session }) {
  const { signOut } = useAuth()
  const [view, navigate] = useHashView()
  const [feedbackId, setFeedbackId] = useState<number | null>(null)
  const [requirementId, setRequirementId] = useState<number | null>(null)
  const [widgetOpen, setWidgetOpen] = useState(false)
  const stats = useFeedbackStats()
  const requirements = useRequirements()
  const activeRequirement = requirements.data?.find(r => r.id === requirementId) ?? null

  const go = (next: View) => { setFeedbackId(null); setRequirementId(null); navigate(next) }
  const openRequirement = (id: number) => { setFeedbackId(null); setRequirementId(id); navigate('requirements') }
  const closeFeedback = useCallback(() => setFeedbackId(null), [])
  const closeRequirement = useCallback(() => setRequirementId(null), [])
  const closeWidget = useCallback(() => setWidgetOpen(false), [])
  const currentUser = session.email.split('@')[0]

  return (
    <div className="app-shell">
      <Sidebar session={session} view={view} newCount={stats.data?.new} requirementCount={requirements.data?.length}
        onNavigate={go} onOpenWidgetSetup={() => setWidgetOpen(true)} onSignOut={() => void signOut()} />
      <main className="main-area">
        <Topbar view={view} feedbackId={feedbackId} email={session.email} />
        {view === 'feedback'
          ? <FeedbackInbox selectedId={feedbackId} currentUser={currentUser} onSelect={setFeedbackId} onOpenWidgetSetup={() => setWidgetOpen(true)} />
          : <RequirementsView requirements={requirements.data} selectedId={requirementId} onSelect={setRequirementId} onBackToInbox={() => go('feedback')} />}
      </main>
      {feedbackId !== null && <FeedbackDrawer feedbackId={feedbackId} onClose={closeFeedback} onOpenRequirement={openRequirement} />}
      {activeRequirement && <RequirementDrawer key={activeRequirement.id} requirement={activeRequirement} onClose={closeRequirement} />}
      {widgetOpen && <WidgetSetupDialog workspaceSlug={session.workspace.slug} onClose={closeWidget} />}
    </div>
  )
}
