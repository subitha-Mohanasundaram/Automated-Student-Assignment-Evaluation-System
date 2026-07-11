import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Topbar from '../components/Topbar'
import { api } from '../lib/api'
import { Eye, Shield, ArrowRight, Loader2, AlertCircle, ListChecks } from 'lucide-react'

function diffClass(d) {
  if (!d) return ''
  const l = d.toLowerCase()
  if (l.includes('easy'))   return 'badge diff-easy'
  if (l.includes('hard'))   return 'badge diff-hard'
  return 'badge diff-medium'
}

function diffBar(d) {
  if (!d) return 'from-slate-600 to-slate-500'
  const l = d.toLowerCase()
  if (l.includes('easy'))   return 'from-emerald-500 to-teal-500'
  if (l.includes('hard'))   return 'from-red-500 to-rose-600'
  return 'from-accent-500 to-orange-500'
}

export default function Assignments() {
  const [assignments, setAssignments] = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState('')

  useEffect(() => {
    api.assignments()
      .then(d => setAssignments(d.assignments || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-dark-800">
      <Topbar />
      <main className="mx-auto max-w-6xl px-4 py-8 page-enter">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 px-3 py-1 text-[11px] font-semibold text-brand-400 mb-3">
              <ListChecks className="h-3 w-3" /> Coding Problems
            </div>
            <h1 className="section-title">Assignments</h1>
            <p className="section-sub">Pick a problem, write your solution, get AI feedback.</p>
          </div>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-8 w-8 text-brand-500 animate-spin" />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {!loading && !error && assignments.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-dark-600 mb-4">
              <ListChecks className="h-8 w-8 text-slate-600" />
            </div>
            <h3 className="text-base font-bold text-slate-300">No assignments yet</h3>
            <p className="mt-1 text-sm text-slate-500">Ask your instructor to publish assignments.</p>
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assignments.map(a => (
            <div key={a.id} className="card card-hover relative overflow-hidden flex flex-col">
              {/* Difficulty bar */}
              <div className={`absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r ${diffBar(a.difficulty)}`} />

              <div className="flex items-start justify-between gap-3 pt-1">
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-[11px] text-slate-500">{a.id}</div>
                  <div className="mt-1 text-[15px] font-bold text-white truncate leading-snug">{a.title}</div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {a.active
                      ? <span className="badge badge-green text-[10px]">Active</span>
                      : <span className="badge badge-yellow text-[10px]">Inactive</span>}
                    {a.difficulty && <span className={`badge text-[10px] ${diffClass(a.difficulty)}`}>{a.difficulty}</span>}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-3 text-[12px] text-slate-500">
                <div className="flex items-center gap-1 rounded-lg bg-dark-600 px-2.5 py-1.5">
                  <Eye className="h-3.5 w-3.5 text-slate-500" />
                  <span className="font-bold text-slate-300">{a.visible_tests}</span> visible
                </div>
                <div className="flex items-center gap-1 rounded-lg bg-dark-600 px-2.5 py-1.5">
                  <Shield className="h-3.5 w-3.5 text-slate-500" />
                  <span className="font-bold text-slate-300">{a.hidden_tests}</span> hidden
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-white/[0.06] flex justify-end">
                <Link to={`/assignment/${a.id}`}
                  className="btn btn-sm btn-primary gap-1">
                  {a.active ? 'Solve' : 'View'} <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
