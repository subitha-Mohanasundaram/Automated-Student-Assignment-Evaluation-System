import { useState, useEffect } from 'react'
import { api } from '../../lib/api'
import { History, RotateCcw, X, Loader2, Clock } from 'lucide-react'

export default function VersionPanel({ workflowId, onRestore, onClose }) {
  const [versions, setVersions] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [restoring, setRestoring] = useState(null)
  const [error,    setError]    = useState(null)

  useEffect(() => { load() }, [workflowId])

  async function load() {
    setLoading(true)
    try {
      const res = await api.workflowVersions(workflowId)
      setVersions(res.versions || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleRestore(v) {
    if (!confirm(`Restore to version saved at ${formatTs(v.version_ts)}?`)) return
    setRestoring(v.version_ts)
    try {
      const res = await api.restoreVersion(workflowId, v.version_ts)
      if (onRestore) onRestore(res.workflow)
    } catch (e) {
      setError(e.message)
    } finally {
      setRestoring(null)
    }
  }

  function formatTs(ts) {
    try {
      return new Date(parseInt(ts, 10) * 1000).toLocaleString()
    } catch {
      return ts
    }
  }

  return (
    <div className="flex flex-col h-full bg-dark-800">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/[0.06]">
        <History className="h-4 w-4 text-brand-400" />
        <span className="text-sm font-bold text-white flex-1">Version History</span>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {loading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-brand-400" />
          </div>
        )}
        {error && (
          <div className="text-xs text-red-400 px-2 py-2">{error}</div>
        )}
        {!loading && versions.length === 0 && (
          <div className="text-center py-8 text-xs text-slate-500">
            No versions saved yet.<br />Versions are created on every save.
          </div>
        )}
        {versions.map((v, i) => (
          <div key={v.version_ts}
            className="flex items-start gap-2 rounded-lg px-2 py-2 hover:bg-white/[0.03] group transition-colors"
          >
            <div className="flex-1 min-w-0">
              {i === 0 && (
                <div className="text-[9px] font-bold uppercase tracking-widest text-brand-400 mb-0.5">Latest</div>
              )}
              <div className="text-xs font-semibold text-white truncate">{v.name}</div>
              <div className="flex items-center gap-1 text-[10px] text-slate-500 mt-0.5">
                <Clock className="h-2.5 w-2.5" />
                {formatTs(v.version_ts)}
              </div>
              <div className="text-[10px] text-slate-600">{v.node_count} nodes</div>
            </div>
            <button
              onClick={() => handleRestore(v)}
              disabled={restoring === v.version_ts}
              className="opacity-0 group-hover:opacity-100 btn btn-secondary btn-sm px-2 py-1 text-[10px] flex-shrink-0 transition-opacity"
            >
              {restoring === v.version_ts
                ? <Loader2 className="h-3 w-3 animate-spin" />
                : <RotateCcw className="h-3 w-3" />}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
