import { useState, useRef } from 'react'
import { api } from '../../lib/api'
import {
  Sparkles, Send, Loader2, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, Wand2, AlertCircle, RotateCcw,
} from 'lucide-react'

const EXAMPLES = [
  'Add retry to all action nodes',
  'Add a 30-second delay after the first node',
  'Replace Gmail with Outlook',
  'Add error handler to HTTP request node',
  'Set timeout on all AI nodes to 60 seconds',
  'Remove the last node',
  'Rename first node to Data Fetcher',
]

export default function AIEditPanel({ workflowId, onApplied }) {
  const [command,   setCommand]   = useState('')
  const [loading,   setLoading]   = useState(false)
  const [preview,   setPreview]   = useState(null)   // { changes, diff_summary, updated_workflow, command_parsed }
  const [error,     setError]     = useState(null)
  const [applying,  setApplying]  = useState(false)
  const [applied,   setApplied]   = useState(false)
  const [diffOpen,  setDiffOpen]  = useState(true)
  const inputRef = useRef(null)

  async function handlePreview(cmd) {
    const text = (cmd || command).trim()
    if (!text) return
    setLoading(true)
    setError(null)
    setPreview(null)
    setApplied(false)
    try {
      const res = await api.aiEditPreview(workflowId, { command: text })
      setPreview(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleApply() {
    if (!preview?.updated_workflow) return
    setApplying(true)
    setError(null)
    try {
      const res = await api.aiEditApply(workflowId, {
        updated_workflow: preview.updated_workflow,
      })
      setApplied(true)
      setPreview(null)
      setCommand('')
      if (onApplied) onApplied(res.workflow)
    } catch (e) {
      setError(e.message)
    } finally {
      setApplying(false)
    }
  }

  function handleDiscard() {
    setPreview(null)
    setError(null)
    setApplied(false)
    inputRef.current?.focus()
  }

  function handleExample(ex) {
    setCommand(ex)
    setPreview(null)
    setError(null)
    setApplied(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const hasPreview = !!preview
  const nodesDelta = hasPreview
    ? (preview.updated_nodes ?? 0) - (preview.original_nodes ?? 0)
    : 0

  return (
    <div className="flex flex-col h-full bg-dark-800 border-t border-white/[0.06]">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]">
        <Wand2 className="h-4 w-4 text-purple-400 flex-shrink-0" />
        <span className="text-sm font-bold text-white flex-1">AI Edit</span>
        <span className="text-[10px] text-slate-500">Natural language workflow editor</span>
      </div>

      <div className="flex flex-1 min-h-0 gap-0">
        {/* Left: input + examples */}
        <div className="flex flex-col w-72 flex-shrink-0 border-r border-white/[0.06] p-4 gap-3">
          {/* Input */}
          <div>
            <label className="label text-[10px]">Edit command</label>
            <div className="flex gap-2">
              <input
                ref={inputRef}
                value={command}
                onChange={e => { setCommand(e.target.value); setApplied(false) }}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handlePreview()}
                placeholder="e.g. Add retry to HTTP request"
                className="input text-xs flex-1"
                disabled={loading || applying}
              />
              <button
                onClick={() => handlePreview()}
                disabled={!command.trim() || loading || applying}
                className="btn btn-primary btn-sm px-2.5 disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0 disabled:shadow-none"
                title="Preview (Enter)"
              >
                {loading
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <Send className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          {/* Applied success */}
          {applied && (
            <div className="flex items-center gap-1.5 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" /> Edit applied!
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-1.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              <AlertCircle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Examples */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1.5">
              Examples
            </div>
            <div className="flex flex-col gap-1">
              {EXAMPLES.map(ex => (
                <button
                  key={ex}
                  onClick={() => handleExample(ex)}
                  className="text-left text-[10px] text-slate-400 hover:text-brand-400 transition-colors leading-relaxed px-1 py-0.5 rounded hover:bg-brand-500/5"
                >
                  → {ex}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right: preview */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {!hasPreview && !loading && (
            <div className="flex flex-col items-center justify-center flex-1 text-center p-6">
              <Sparkles className="h-8 w-8 text-purple-400/40 mb-3" />
              <div className="text-sm font-semibold text-slate-400 mb-1">
                Type an edit command
              </div>
              <div className="text-xs text-slate-600">
                The AI will preview the changes before you apply them.
              </div>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center flex-1 gap-3">
              <Loader2 className="h-6 w-6 text-purple-400 animate-spin" />
              <div className="text-xs text-slate-400">Generating preview…</div>
            </div>
          )}

          {hasPreview && (
            <div className="flex flex-col flex-1 overflow-y-auto p-4 gap-4">
              {/* Parsed command badge */}
              <div className="flex items-start gap-2 rounded-lg border border-purple-500/25 bg-purple-500/10 px-3 py-2.5">
                <Wand2 className="h-3.5 w-3.5 text-purple-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-widest text-purple-400 mb-0.5">
                    Parsed as
                  </div>
                  <div className="text-xs text-slate-200 break-words">
                    {preview.command_parsed}
                  </div>
                </div>
              </div>

              {/* Stats row */}
              <div className="flex gap-3">
                <Stat label="Changes" value={preview.changes?.length ?? 0} />
                <Stat
                  label="Node delta"
                  value={nodesDelta === 0 ? '±0' : nodesDelta > 0 ? `+${nodesDelta}` : nodesDelta}
                  valueClass={nodesDelta > 0 ? 'text-emerald-400' : nodesDelta < 0 ? 'text-red-400' : 'text-slate-400'}
                />
                <Stat label="Nodes after" value={preview.updated_nodes ?? '?'} />
              </div>

              {/* Change list */}
              {preview.changes?.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                    Changes
                  </div>
                  {preview.changes.map((c, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-xs text-slate-300">
                      <span className="text-emerald-400 font-bold mt-0.5">+</span>
                      <span>{c}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Diff summary collapsible */}
              {preview.diff_summary && (
                <div className="rounded-lg border border-white/[0.06] overflow-hidden">
                  <button
                    onClick={() => setDiffOpen(o => !o)}
                    className="flex items-center gap-2 w-full px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-slate-500 hover:text-slate-300 transition-colors bg-dark-700"
                  >
                    Diff summary
                    {diffOpen
                      ? <ChevronUp className="h-3 w-3 ml-auto" />
                      : <ChevronDown className="h-3 w-3 ml-auto" />}
                  </button>
                  {diffOpen && (
                    <pre className="px-3 py-2 text-[10px] font-mono text-slate-400 whitespace-pre-wrap bg-dark-900/50">
                      {preview.diff_summary}
                    </pre>
                  )}
                </div>
              )}

              {/* Apply / Discard */}
              <div className="flex gap-2 pt-1 border-t border-white/[0.06] mt-auto">
                <button
                  onClick={handleApply}
                  disabled={applying}
                  className="btn btn-primary flex-1 disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0 disabled:shadow-none"
                >
                  {applying
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <CheckCircle2 className="h-4 w-4" />}
                  Apply Changes
                </button>
                <button
                  onClick={handleDiscard}
                  disabled={applying}
                  className="btn btn-secondary"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Discard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, valueClass = 'text-white' }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-white/[0.06] bg-dark-700 px-4 py-2 min-w-[70px]">
      <span className={`text-base font-extrabold ${valueClass}`}>{value}</span>
      <span className="text-[9px] text-slate-500 uppercase tracking-widest">{label}</span>
    </div>
  )
}
