import { useState } from 'react'
import { api } from '../../lib/api'
import {
  Sparkles, Loader2, AlertCircle, CheckCircle2, X,
  FileJson, Download, Plus,
} from 'lucide-react'

export default function AIGeneratePanel({ onGenerated, onClose }) {
  const [intent,   setIntent]   = useState('')
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState(null)

  async function handleGenerate() {
    if (!intent.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.generateWorkflow({ intent })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleLoad() {
    if (!result?.workflow) return
    // Save generated workflow then navigate to builder
    try {
      const saved = await api.createWorkflow({
        name: result.workflow.name || 'AI Generated Workflow',
        description: result.workflow.description || '',
        nodes: result.workflow.nodes || [],
        edges: result.workflow.edges || [],
      })
      if (onGenerated) onGenerated(saved)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark-900/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl rounded-2xl border border-white/[0.08] bg-dark-800 shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-white/[0.06]">
          <Sparkles className="h-5 w-5 text-purple-400" />
          <span className="font-bold text-white flex-1">Generate Workflow from AI</span>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Intent input */}
          <div>
            <label className="label">Describe your workflow</label>
            <textarea
              value={intent}
              onChange={e => { setIntent(e.target.value); setError(null); setResult(null) }}
              onKeyDown={e => e.key === 'Enter' && e.ctrlKey && handleGenerate()}
              placeholder="e.g. When a GitHub PR is merged, post to Slack and create a Jira ticket"
              rows={3}
              className="input w-full resize-none text-sm"
              disabled={loading}
            />
            <p className="text-[10px] text-slate-500 mt-1">Ctrl+Enter to generate</p>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              <AlertCircle className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" /> {error}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" />
                Generated <strong>{result.workflow?.name}</strong> with {result.node_count} nodes
              </div>

              {result.explanation && (
                <div className="rounded-lg border border-white/[0.06] bg-dark-700 p-3 text-xs text-slate-300 leading-relaxed">
                  {result.explanation}
                </div>
              )}

              <div className="flex items-center gap-2 text-xs text-slate-500">
                <FileJson className="h-3.5 w-3.5" />
                {result.node_count} nodes · {result.workflow?.name}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/[0.06] flex gap-3">
          <button
            onClick={handleGenerate}
            disabled={!intent.trim() || loading}
            className="btn btn-primary flex-1 disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0 disabled:shadow-none"
          >
            {loading
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
              : <><Sparkles className="h-4 w-4" /> Generate</>}
          </button>
          {result && (
            <button onClick={handleLoad} className="btn btn-secondary flex-1">
              <Plus className="h-4 w-4" /> Load into Builder
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
