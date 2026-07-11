import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Topbar from '../components/Topbar'
import AIFeedback from '../components/AIFeedback'
import { api } from '../lib/api'
import { Loader2, Trophy, Code2, LayoutDashboard, Eye, Shield, CheckCircle, XCircle, FlaskConical } from 'lucide-react'

export default function Report() {
  const { id } = useParams()
  const [report, setReport]   = useState(null)
  const [ev, setEv]           = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    async function load() {
      try {
        const evData = await api.evaluation(parseInt(id))
        setEv(evData)
        const rData = await api.report(parseInt(id))
        setReport(rData)
      } catch (e) { setError(e.message) }
      finally { setLoading(false) }
    }
    load()
  }, [id])

  if (loading) return (
    <div className="min-h-screen bg-dark-800 flex items-center justify-center">
      <Loader2 className="h-10 w-10 text-brand-500 animate-spin" />
    </div>
  )

  if (error) return (
    <div className="min-h-screen bg-dark-800">
      <Topbar />
      <div className="mx-auto max-w-2xl px-4 py-10">
        <div className="card border-red-500/20 bg-red-500/10 text-red-300">{error}</div>
      </div>
    </div>
  )

  const analysis   = report?.analysis || {}
  const results    = analysis.results || {}
  const ai_feedback = analysis.ai_feedback || null
  const score      = parseFloat(ev?.score || results?.score || 0)
  const passed     = parseInt(results.passed_cases || 0)
  const total      = parseInt(results.total_test_cases || 0)
  const visible    = results.visible || {}
  const hidden     = results.hidden || {}
  const cases      = (results.case_results || []).filter(c => c.visibility === 'visible')
  const student    = report?.student_name || ev?.username || ''
  const problem_id = ev?.problem_id || report?.problem_id || ''
  const language   = ev?.language || report?.language || ''

  const scoreBg = score >= 80
    ? 'from-emerald-600 to-teal-700 shadow-emerald-500/20'
    : score >= 50
    ? 'from-amber-500 to-orange-600 shadow-amber-500/20'
    : 'from-red-600 to-rose-700 shadow-red-500/20'

  return (
    <div className="min-h-screen bg-dark-800">
      <Topbar />
      <main className="mx-auto max-w-5xl px-4 py-8 page-enter">

        {/* Hero banner */}
        <div className={`relative overflow-hidden rounded-2xl bg-gradient-to-br ${scoreBg} shadow-xl p-6 text-white mb-6`}>
          <div className="absolute inset-0 opacity-[0.05]"
               style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '24px 24px' }} />
          <div className="relative flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="text-xs font-semibold text-white/60 uppercase tracking-widest">Evaluation Report</div>
              <div className="mt-1 text-xl font-extrabold">{student || 'Student'}</div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-white/15 px-3 py-1 font-semibold">{problem_id}</span>
                <span className="rounded-full bg-white/15 px-3 py-1 font-semibold">{language}</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-white/60 mb-1">Score</div>
              <div className="text-5xl font-black font-mono">{score}</div>
              <div className="text-xs text-white/50 mt-1">{passed}/{total} passed</div>
            </div>
          </div>
          <div className="relative mt-4 h-1.5 w-full rounded-full bg-white/20 overflow-hidden">
            <div className="h-full rounded-full bg-white/80 transition-all duration-1000" style={{ width: `${Math.min(score, 100)}%` }} />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
          {/* Sidebar */}
          <div className="space-y-4">
            <div className="card">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-3">Breakdown</div>
              <div className="space-y-3">
                {[
                  { label: 'Visible', icon: Eye, val: visible, color: 'bg-sky-500' },
                  { label: 'Hidden', icon: Shield, val: hidden, color: 'bg-violet-500' },
                ].map(({ label, icon: Icon, val, color }) => (
                  <div key={label}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-slate-400 flex items-center gap-1"><Icon className="h-3 w-3" /> {label}</span>
                      <span className="font-mono font-bold text-slate-200">{val.passed || 0}/{val.total || 0}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-dark-600 overflow-hidden">
                      <div className={`h-full rounded-full ${color}`} style={{ width: `${val.total ? Math.round((val.passed/val.total)*100) : 0}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-white/[0.06] space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Anti-Cheat</span>
                  {results.anti_cheat?.passed !== false
                    ? <span className="badge badge-green text-[10px]">PASS</span>
                    : <span className="badge badge-red text-[10px]">FAIL</span>}
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Plagiarism</span>
                  {results.plagiarism?.detected
                    ? <span className="badge badge-red text-[10px]">Flagged</span>
                    : <span className="badge badge-green text-[10px]">Clear</span>}
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <Link to={`/assignment/${problem_id}`} className="btn btn-secondary w-full justify-center">
                <Code2 className="h-4 w-4" /> Resubmit
              </Link>
              <Link to="/me" className="btn btn-secondary w-full justify-center">
                <LayoutDashboard className="h-4 w-4" /> Dashboard
              </Link>
            </div>
          </div>

          {/* Main */}
          <div className="lg:col-span-3 space-y-5">
            {/* AI Feedback */}
            {ai_feedback && <AIFeedback feedback={ai_feedback} />}

            {/* Test results */}
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <FlaskConical className="h-4 w-4 text-sky-400" /> Visible Test Results
                </h2>
                <span className="badge badge-blue text-[10px]">Hidden not shown</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] font-bold uppercase tracking-wider text-slate-500 border-b border-white/[0.06]">
                      <th className="pb-2 pr-3 w-8">#</th>
                      <th className="pb-2 pr-3">Input</th>
                      <th className="pb-2 pr-3">Expected</th>
                      <th className="pb-2 pr-3">Output</th>
                      <th className="pb-2 w-16">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c, i) => (
                      <tr key={i} className={`border-b border-white/[0.04] ${c.passed ? 'bg-emerald-500/[0.03]' : 'bg-red-500/[0.03]'}`}>
                        <td className="py-2 pr-3 font-mono text-slate-500">{i + 1}</td>
                        <td className="py-2 pr-3"><pre className="rounded-lg bg-dark-700 px-2 py-1 text-xs text-slate-200 max-w-[130px] overflow-x-auto">{c.input}</pre></td>
                        <td className="py-2 pr-3"><pre className="rounded-lg bg-dark-700 px-2 py-1 text-xs text-slate-200 max-w-[100px] overflow-x-auto">{c.expected}</pre></td>
                        <td className="py-2 pr-3"><pre className="rounded-lg bg-dark-700 px-2 py-1 text-xs text-slate-200 max-w-[100px] overflow-x-auto">{c.actual}</pre></td>
                        <td className="py-2">
                          {c.passed
                            ? <span className="badge badge-green text-[10px] gap-1"><CheckCircle className="h-3 w-3" />PASS</span>
                            : <span className="badge badge-red text-[10px] gap-1"><XCircle className="h-3 w-3" />FAIL</span>}
                        </td>
                      </tr>
                    ))}
                    {cases.length === 0 && (
                      <tr><td colSpan={5} className="py-8 text-center text-slate-500">No visible test cases.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
