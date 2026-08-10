import { useEffect, useRef, useState } from 'react'
import {
  Play, Square, RefreshCw, ChevronDown, ChevronUp,
  CheckCircle2, XCircle, Clock, Loader2, AlertCircle,
  Terminal, Activity
} from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL || ''

function getToken() {
  return localStorage.getItem('token') || ''
}

// ── Status helpers ────────────────────────────────────────────────
const STATUS_STYLE = {
  pending:   { icon: Clock,        cls: 'text-slate-400',  badge: 'badge-grey' },
  running:   { icon: Loader2,      cls: 'text-brand-400 animate-spin', badge: 'badge-teal' },
  succeeded: { icon: CheckCircle2, cls: 'text-emerald-400', badge: 'badge-green' },
  failed:    { icon: XCircle,      cls: 'text-red-400',    badge: 'badge-red' },
  timed_out: { icon: AlertCircle,  cls: 'text-amber-400',  badge: 'badge-yellow' },
  skipped:   { icon: ChevronDown,  cls: 'text-slate-500',  badge: 'badge-grey' },
}

const LOG_LEVEL_CLS = {
  info:    'text-slate-300',
  warning: 'text-amber-400',
  error:   'text-red-400',
  debug:   'text-slate-500',
}

// ── Node state row ───────────────────────────────────────────────
function NodeStateRow({ nodeId, state }) {
  const s   = STATUS_STYLE[state.status] || STATUS_STYLE.pending
  const Ico = s.icon
  const dur = state.started_at && state.finished_at
    ? `${((new Date(state.finished_at) - new Date(state.started_at))).toFixed(0)}ms`
    : null

  return (
    <div className="flex items-center gap-2 py-1 border-b border-white/[0.03] last:border-0">
      <Ico className={`h-3.5 w-3.5 flex-shrink-0 ${s.cls}`} />
      <span className="flex-1 text-xs font-mono text-slate-300 truncate">{nodeId}</span>
      {state.attempt > 1 && (
        <span className="text-[9px] text-amber-400">×{state.attempt}</span>
      )}
      {dur && <span className="text-[10px] text-slate-500">{dur}</span>}
      <span className={`badge ${s.badge} text-[9px]`}>{state.status}</span>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────
export default function ExecutionPanel({ workflowId, onNodeStatusChange }) {
  const [runId,    setRunId]    = useState(null)
  const [record,   setRecord]   = useState(null)
  const [running,  setRunning]  = useState(false)
  const [dryRun,   setDryRun]   = useState(true)
  const [error,    setError]    = useState(null)
  const [logsOpen, setLogsOpen] = useState(true)
  const [runs,     setRuns]     = useState([])
  const [tab,      setTab]      = useState('live') // 'live' | 'history'

  const esRef    = useRef(null)
  const logEndRef = useRef(null)

  // Auto-scroll logs
  useEffect(() => {
    if (logsOpen && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [record?.logs?.length])

  // Load run history
  useEffect(() => {
    if (tab === 'history') loadHistory()
  }, [tab])

  // Notify parent of node status changes
  useEffect(() => {
    if (!record?.node_states || !onNodeStatusChange) return
    onNodeStatusChange(record.node_states)
  }, [record?.node_states])

  // Cleanup SSE on unmount
  useEffect(() => () => esRef.current?.close(), [])

  async function loadHistory() {
    try {
      const token = getToken()
      const res   = await fetch(`${BASE}/api/workflows/${workflowId}/runs`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      })
      const data = await res.json()
      setRuns(data.runs || [])
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleRun() {
    setError(null)
    setRecord(null)
    setRunning(true)
    setTab('live')

    try {
      const token = getToken()
      const res = await fetch(`${BASE}/api/workflows/${workflowId}/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({ dry_run: dryRun }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.error || `HTTP ${res.status}`)
      }

      const { run_id } = await res.json()
      setRunId(run_id)
      subscribeSSE(run_id)

    } catch (e) {
      setError(e.message)
      setRunning(false)
    }
  }

  function subscribeSSE(rid) {
    esRef.current?.close()

    const token = getToken()
    const url   = `${BASE}/api/runs/${rid}/stream${token ? `?token=${token}` : ''}`
    const es    = new EventSource(url)
    esRef.current = es

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setRecord(data)
        const terminal = new Set(['succeeded', 'failed', 'timed_out', 'cancelled'])
        if (terminal.has(data.status)) {
          setRunning(false)
          es.close()
        }
      } catch {}
    }

    es.onerror = () => {
      setRunning(false)
      es.close()
    }
  }

  function handleStop() {
    esRef.current?.close()
    setRunning(false)
  }

  async function handleLoadRun(rid) {
    setTab('live')
    setRunId(rid)
    try {
      const token = getToken()
      const res   = await fetch(`${BASE}/api/runs/${rid}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      })
      const data = await res.json()
      setRecord(data)
    } catch (e) {
      setError(e.message)
    }
  }

  const status     = record?.status
  const st         = STATUS_STYLE[status] || STATUS_STYLE.pending
  const StatusIcon = st.icon
  const nodeStates = record?.node_states || {}
  const logs       = record?.logs        || []

  return (
    <div className="flex flex-col h-full border-t border-white/[0.06] bg-dark-800">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06]">
        <Activity className="h-4 w-4 text-brand-400 flex-shrink-0" />
        <span className="text-sm font-bold text-white flex-1">Execution</span>

        {status && (
          <span className={`badge ${st.badge} gap-1`}>
            <StatusIcon className={`h-3 w-3 ${running ? 'animate-spin' : ''}`} />
            {status}
          </span>
        )}

        {/* Dry-run toggle */}
        <button
          onClick={() => setDryRun(d => !d)}
          className={`text-[10px] font-bold px-2 py-1 rounded-md border transition-all
            ${dryRun
              ? 'border-brand-500/40 bg-brand-500/10 text-brand-400'
              : 'border-amber-500/40 bg-amber-500/10 text-amber-400'}`}
        >
          {dryRun ? 'DRY RUN' : 'LIVE'}
        </button>

        {/* Run / Stop */}
        {running ? (
          <button onClick={handleStop} className="btn btn-sm border border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20">
            <Square className="h-3.5 w-3.5" /> Stop
          </button>
        ) : (
          <button onClick={handleRun} className="btn btn-primary btn-sm">
            <Play className="h-3.5 w-3.5" /> Run
          </button>
        )}

        {/* Tabs */}
        <div className="flex rounded-lg overflow-hidden border border-white/[0.06]">
          {['live', 'history'].map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1 text-[10px] font-semibold uppercase tracking-wide transition-colors
                ${tab === t ? 'bg-brand-500/20 text-brand-400' : 'text-slate-500 hover:text-slate-300'}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mt-2 flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" /> {error}
        </div>
      )}

      {/* Content */}
      {tab === 'history' ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-1">
          {runs.length === 0 && (
            <div className="text-center py-8 text-slate-500 text-xs">No runs yet</div>
          )}
          {runs.map(r => {
            const rs = STATUS_STYLE[r.status] || STATUS_STYLE.pending
            const RI = rs.icon
            return (
              <button
                key={r.run_id}
                onClick={() => handleLoadRun(r.run_id)}
                className="w-full flex items-center gap-3 rounded-lg border border-white/[0.06] bg-dark-700 px-3 py-2 text-left hover:border-brand-500/30 transition-colors"
              >
                <RI className={`h-3.5 w-3.5 flex-shrink-0 ${rs.cls}`} />
                <span className="flex-1 text-xs font-mono text-slate-300 truncate">{r.run_id}</span>
                <span className={`badge ${rs.badge} text-[9px]`}>{r.status}</span>
                <span className="text-[10px] text-slate-500">
                  {r.started_at ? new Date(r.started_at).toLocaleTimeString() : ''}
                </span>
              </button>
            )
          })}
        </div>
      ) : (
        <div className="flex flex-1 min-h-0 gap-0">
          {/* Node states */}
          <div className="w-56 flex-shrink-0 border-r border-white/[0.06] overflow-y-auto p-3">
            <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Nodes</div>
            {Object.keys(nodeStates).length === 0 && !running && (
              <div className="text-[10px] text-slate-600 text-center py-4">Run to see node status</div>
            )}
            {Object.entries(nodeStates).map(([nid, state]) => (
              <NodeStateRow key={nid} nodeId={nid} state={state} />
            ))}
          </div>

          {/* Logs */}
          <div className="flex-1 flex flex-col min-w-0">
            <button
              onClick={() => setLogsOpen(o => !o)}
              className="flex items-center gap-2 px-4 py-1.5 border-b border-white/[0.04] text-[10px] font-bold uppercase tracking-widest text-slate-500 hover:text-slate-300 transition-colors"
            >
              <Terminal className="h-3 w-3" /> Logs
              {logsOpen ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
            </button>

            {logsOpen && (
              <div className="flex-1 overflow-y-auto p-3 font-mono text-[10px] space-y-0.5">
                {logs.length === 0 && (
                  <div className="text-slate-600 py-4 text-center">No logs yet</div>
                )}
                {logs.map((entry, i) => (
                  <div key={i} className={`flex gap-2 leading-relaxed ${LOG_LEVEL_CLS[entry.level] || 'text-slate-400'}`}>
                    <span className="text-slate-600 flex-shrink-0">
                      {new Date(entry.ts).toLocaleTimeString('en', { hour12: false })}
                    </span>
                    <span className="break-all">{entry.msg}</span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
