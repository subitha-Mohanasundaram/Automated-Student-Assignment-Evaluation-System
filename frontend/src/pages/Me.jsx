import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Topbar from '../components/Topbar'
import { api } from '../lib/api'
import { getUser } from '../lib/auth'
import { FileText, Code2, Trash2, Loader2, Target, Send, Trophy } from 'lucide-react'

export default function Me() {
  const user = getUser()
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.me().then(setData).catch(console.error).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="min-h-screen bg-dark-800 flex items-center justify-center">
      <Loader2 className="h-10 w-10 text-brand-500 animate-spin" />
    </div>
  )

  const best  = data?.best_scores || []
  const subs  = data?.submissions || []
  const initials = user?.username?.slice(0, 2).toUpperCase() || '??'

  return (
    <div className="min-h-screen bg-dark-800">
      <Topbar />
      <main className="mx-auto max-w-6xl px-4 py-8 page-enter">

        {/* Profile hero */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-dark-700 via-dark-600 to-dark-700 border border-white/[0.07] p-6 md:p-8 mb-6">
          <div className="absolute inset-0 opacity-[0.03]"
               style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, white 1px, transparent 0)', backgroundSize: '28px 28px' }} />
          <div className="relative flex items-center gap-5">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-600 text-xl font-black text-white shadow-lg shadow-brand-500/30 shrink-0">
              {initials}
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest">My Profile</div>
              <div className="mt-0.5 text-2xl font-extrabold text-white">{user?.username}</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className={`badge ${user?.role === 'admin' ? 'badge-orange' : 'badge-teal'}`}>{user?.role}</span>
                <span className="badge badge-grey gap-1"><Send className="h-3 w-3" /> {subs.length} submissions</span>
              </div>
            </div>
          </div>
          <div className="relative mt-6 grid grid-cols-3 gap-3">
            {[
              { label: 'Solved', value: best.length, icon: Target },
              { label: 'Submissions', value: subs.length, icon: Send },
              { label: 'Best Score', value: best.length ? Math.max(...best.map(b => b.score)) : '—', icon: Trophy },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="rounded-xl bg-white/[0.06] px-4 py-3">
                <div className="text-xs font-semibold text-white/50 uppercase tracking-wider">{label}</div>
                <div className="mt-1 text-2xl font-black font-mono text-white">{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
          {/* Best scores */}
          <div className="card lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-bold text-white">Best Scores</h2>
              <Link to="/assignments" className="btn btn-sm btn-secondary">Solve More</Link>
            </div>
            <div className="space-y-2">
              {best.map(row => {
                const pct = Math.min(row.score, 100)
                const bar = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-accent-500' : 'bg-red-500'
                const sc  = pct >= 80 ? 'badge-green' : pct >= 50 ? 'badge-yellow' : 'badge-red'
                return (
                  <div key={row.problem_id} className="rounded-xl border border-white/[0.06] bg-dark-600 p-3 hover:border-brand-500/30 transition">
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <span className="font-mono text-[12px] font-semibold text-slate-200 truncate">{row.problem_id}</span>
                      <span className={`badge ${sc} text-[11px] font-mono shrink-0`}>{row.score}</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-dark-700 overflow-hidden">
                      <div className={`h-full rounded-full ${bar}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
              {best.length === 0 && (
                <div className="py-10 text-center text-slate-500 text-sm">No submissions yet</div>
              )}
            </div>
          </div>

          {/* Submission history */}
          <div className="card lg:col-span-3">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-bold text-white">Submission History</h2>
              <span className="text-xs text-slate-500">{subs.length} recent</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] font-bold uppercase tracking-wider text-slate-500 border-b border-white/[0.06]">
                    <th className="pb-2">Problem</th>
                    <th className="pb-2">Lang</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Score</th>
                    <th className="pb-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {subs.map(s => {
                    const sc = parseFloat(s.score || 0)
                    const scoreColor = sc >= 80 ? 'text-emerald-400' : sc >= 50 ? 'text-accent-500' : 'text-red-400'
                    return (
                      <tr key={s.evaluation_id} className="border-b border-white/[0.04]">
                        <td className="py-2.5 font-mono text-[12px] text-slate-200">{s.problem_id}</td>
                        <td className="py-2.5"><span className="badge badge-grey text-[10px]">{s.language}</span></td>
                        <td className="py-2.5">
                          {s.status === 'completed' && <span className="badge badge-green text-[10px]">Done</span>}
                          {s.status === 'failed'    && <span className="badge badge-red text-[10px]">Failed</span>}
                          {!['completed','failed'].includes(s.status) && <span className="badge badge-yellow text-[10px]">{s.status}</span>}
                        </td>
                        <td className={`py-2.5 font-mono font-bold text-[13px] ${scoreColor}`}>{s.score}</td>
                        <td className="py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {s.report_path && (
                              <Link to={`/report/${s.evaluation_id}`} className="btn btn-sm btn-secondary py-1 px-2">
                                <FileText className="h-3 w-3" />
                              </Link>
                            )}
                            <Link to={`/assignment/${s.problem_id}`} className="btn btn-sm btn-secondary py-1 px-2">
                              <Code2 className="h-3 w-3" />
                            </Link>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {subs.length === 0 && (
                    <tr><td colSpan={5} className="py-10 text-center text-slate-500">No evaluations yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
