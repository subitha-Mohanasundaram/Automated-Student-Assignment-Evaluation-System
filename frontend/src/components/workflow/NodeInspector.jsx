import { useState, useEffect } from 'react'
import { X, Save, Trash2, ToggleLeft } from 'lucide-react'
import { TYPE_META } from './CustomNodes'

export default function NodeInspector({ node, onChange, onDelete, onClose }) {
  const [label,       setLabel]       = useState('')
  const [description, setDescription] = useState('')
  const [integration, setIntegration] = useState('')
  const [hasRetry,    setHasRetry]    = useState(false)
  const [hasTimeout,  setHasTimeout]  = useState(false)
  const [dirty,       setDirty]       = useState(false)

  // Sync when selection changes
  useEffect(() => {
    if (!node) return
    setLabel(node.data.label || '')
    setDescription(node.data.description || '')
    setIntegration(node.data.integration || '')
    setHasRetry(node.data.hasRetry   || false)
    setHasTimeout(node.data.hasTimeout || false)
    setDirty(false)
  }, [node?.id])

  if (!node) return null

  const meta = TYPE_META[node.data.nodeType] || TYPE_META.action
  const Icon = meta.icon

  function mark(fn) {
    return (...args) => { fn(...args); setDirty(true) }
  }

  function handleSave() {
    onChange(node.id, { label, description, integration, hasRetry, hasTimeout })
    setDirty(false)
  }

  return (
    <aside className="flex flex-col w-64 flex-shrink-0 rounded-xl border border-white/[0.07] bg-dark-700 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${meta.iconBg}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{meta.label}</div>
          <div className="text-xs font-bold text-white truncate">{label || 'Unnamed'}</div>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors ml-1">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Fields */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <label className="label">Name</label>
          <input
            className="input"
            value={label}
            onChange={mark(e => setLabel(e.target.value))}
            placeholder="Node name"
          />
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            className="input resize-none"
            rows={3}
            value={description}
            onChange={mark(e => setDescription(e.target.value))}
            placeholder="What does this node do?"
          />
        </div>

        {node.data.nodeType === 'action' && (
          <div>
            <label className="label">Integration</label>
            <input
              className="input"
              value={integration}
              onChange={mark(e => setIntegration(e.target.value))}
              placeholder="e.g. google_sheets, slack"
            />
          </div>
        )}

        {/* Reliability toggles */}
        <div className="space-y-2">
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Reliability</div>

          <Toggle label="Retry on failure" checked={hasRetry}
            onChange={mark(v => setHasRetry(v))} />
          <Toggle label="Timeout limit"    checked={hasTimeout}
            onChange={mark(v => setHasTimeout(v))} />
        </div>

        {/* Status read-only */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Status</div>
          <StatusBadge status={node.data.status || 'idle'} />
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center gap-2 border-t border-white/[0.06] px-4 py-3">
        <button
          onClick={handleSave}
          disabled={!dirty}
          className="btn btn-primary btn-sm flex-1 disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0 disabled:shadow-none"
        >
          <Save className="h-3.5 w-3.5" /> Save
        </button>
        <button
          onClick={() => onDelete(node.id)}
          className="btn btn-sm border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </aside>
  )
}

function Toggle({ label, checked, onChange }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-xs font-semibold transition-all
        ${checked
          ? 'border-brand-500/40 bg-brand-500/10 text-brand-400'
          : 'border-white/[0.06] bg-dark-600 text-slate-400 hover:border-white/10'}`}
    >
      {label}
      <span className={`flex h-4 w-7 items-center rounded-full transition-colors ${checked ? 'bg-brand-500' : 'bg-slate-600'}`}>
        <span className={`h-3 w-3 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-3.5' : 'translate-x-0.5'}`} />
      </span>
    </button>
  )
}

function StatusBadge({ status }) {
  const map = {
    idle:    'badge-grey',
    running: 'badge-teal',
    success: 'badge-green',
    failed:  'badge-red',
  }
  return <span className={`badge ${map[status] || 'badge-grey'}`}>{status}</span>
}
