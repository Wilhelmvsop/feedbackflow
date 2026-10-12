import { useEffect, useRef, useState } from 'react'
import { Check, Copy, X } from 'lucide-react'

export function WidgetSetupDialog({ workspaceSlug, onClose }: { workspaceSlug: string; onClose: () => void }) {
  const origin = window.location.origin
  const snippet = `<script src="${origin}/feedbackflow.js" data-api="${origin}/api" data-project="${workspaceSlug}"></script>`
  const [copied, setCopied] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(snippet)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <>
      <button className="drawer-scrim" aria-label="Close widget setup" onClick={onClose} />
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="widget-setup-title">
        <div className="dialog-head">
          <h2 id="widget-setup-title">Collect feedback from your product</h2>
          <button ref={closeRef} className="drawer-close" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <p className="muted">Paste this snippet before <code>&lt;/body&gt;</code> on any page. Submissions land in this inbox.</p>
        <pre className="snippet"><code>{snippet}</code></pre>
        <ul className="dialog-notes">
          <li>The widget only sends the typed message, a category, and — if the visitor opts in — the page path.</li>
          <li>Embedding on another domain? Add that origin to <code>CORS_ORIGINS</code> on the server.</li>
        </ul>
        <div className="dialog-actions">
          <button className="secondary dialog-secondary" onClick={onClose}>Close</button>
          <button className="primary" onClick={copy}>{copied ? <Check size={15} /> : <Copy size={15} />}{copied ? 'Copied' : 'Copy snippet'}</button>
        </div>
      </div>
    </>
  )
}
