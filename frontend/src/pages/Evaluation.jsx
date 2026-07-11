import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Topbar from '../components/Topbar'
import { api } from '../lib/api'
import { CheckCircle, XCircle, Loader2, FileText, Code2, Trophy, LayoutDashboard } from 'lucide-react'

const STEPS = ['Queued', 'Running tests', 'Evaluating', 'Generating feedback', 'Completed']

function stepIndex(status) {
  if (status === 'completed') return 4
  if (status === 'failed')    return 2
  if (status === 'running')   return 1
  return 0
}

export default function Evaluation() {
  const { id } = useParams()
  const [ev, setEv] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let interval
    async function poll() {
      try {
        const data = await api.evaluation(parseInt(id))
        setEv(data)
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval)
        }
      } catch (e) { setError(e.message) }
    }
    poll()
    interval = setInterval(poll, 3000)
    return () => clearInterval(interval)
  }, [id])

  const idx      = ev ? stepIndex(ev.status) : 0
  const progress = Math.round((idx / (STEPS.length - 1)) * 100)
  const score    = ev ? parseFloat(ev.score || 0) : 0
  const scoreColor = score >= 80 ? 'text-emerald-400' : score >= 50 ? 'text-accent-500' : 'text-red-400'

  return (
    <div className="min-h-screen bg-dark-800">
      <Topbar />
      <main className="mx-auto max-w-2xl px-4 py-10 page-enter">
        <div className="card">
          {/* Header */}
          <div className="flex items-start justify-between gap-4 pb-5 border-b border-white/[0.06]">
            <div>
              <div className="font-mono text-[11px] text-slate-500">Evaluation #{id}</div>
              <h1 className="mt-1 text-xl font-extrabold text-white">Evaluation Status</h1>
              {ev && (
                <div className="mt-2 flex items-center gap-3 text-sm text-slate-400">
                  <span className="font-mono font-semibold text-slate-300">{ev.problem_id}</span>
                  <span>·</span>
                  <span className="font-mono">{ev.language}</span>
                </div>
              )}
            </div>
            <div className="text-right">
              {ev?.status === 'completed' && <span className="badge badge-green"><CheckCircle className="h-3 w-3" /> Completed</span>}
              {ev?.status === 'failed'    && <span className="badge badge-red"><XCircle className="h-3 w-3" /> Failed</span>}
              {ev && !['completed','failed'].includes(ev.status) && (
                <span className="badge badge-yellow"><Loader2 className="h-3 w-3 animate-spin" /> {ev.status}</span>
              )}
              {ev?.status === 'completed' && (
                <div className="mt-2">
                  <div className="text-[11px] text-slate-500">Score</div>
                  <div className={`font-mono text-3xl font-black ${scoreColor}`}>{score}</div>
                </div>
              )}
            </div>
          </div>

          {/* Error */}
          {ev?.error && (
            <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {ev.error}
            </div>
          )}

          {/* Progress */}
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-bold text-slate-300">Progress</div>
              <div className="text-xs text-slate-500">{STEPS[idx]}</div>
            </div>
            <div className="h-2 w-full rounded-full bg-dark-600 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400 transition-all duration-700"
                   style={{ width: `${progress}%` }} />
            </div>

            {/* Steps */}
            <div className="mt-4 grid grid-cols-5 gap-1">
              {STEPS.map((name, i) => (
                <div key={name} className={`rounded-lg px-2 py-2 text-center border
                  ${i < idx  ? 'border-emerald-500/30 bg-emerald-500/10' :
                    i === idx ? 'border-brand-500/30 bg-brand-500/10'    :
                                'border-white/[0.05] bg-dark-600'}`}>
                  <div className="text-[10px] font-bold leading-tight
                    ${i < idx ? 'text-emerald-400' : i === idx ? 'text-brand-400' : 'text-slate-600'}">
                    {i < idx ? '✓' : i === idx ? '…' : '·'}
                  </div>
                  <div className={`text-[9px] font-semibold mt-0.5 leading-tight
                    ${i < idx ? 'text-emerald-400' : i === idx ? 'text-brand-400' : 'text-slate-600'}`}>
                    {name}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="mt-6 flex flex-wrap gap-2 pt-5 border-t border-white/[0.06]">
            {ev?.status === 'completed' && ev.report_path && (
              <Link to={`/report/${id}`} className="btn btn-primary">
                <FileText className="h-4 w-4" /> View Report
              </Link>
            )}
            {ev && (
              <Link to={`/assignment/${ev.problem_id}`} className="btn btn-secondary">
                <Code2 className="h-4 w-4" /> Edit &amp; Resubmit
              </Link>
            )}
            <Link to="/me" className="btn btn-secondary">
              <LayoutDashboard className="h-4 w-4" /> Dashboard
            </Link>
          </div>

          {!ev && !error && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-8 w-8 text-brand-500 animate-spin" />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
