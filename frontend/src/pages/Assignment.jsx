import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Topbar from '../components/Topbar'
import { api } from '../lib/api'
import { Loader2, Send, RotateCcw, Trophy, AlertTriangle } from 'lucide-react'

const STARTERS = {
  python:     'def solve(s: str) -> str:\n    # Write your solution here\n    pass\n',
  java:       'public class Solution {\n    public static String solve(String s) {\n        // Write your solution here\n        return "";\n    }\n}\n',
  javascript: 'function solve(s) {\n    // Write your solution here\n    return "";\n}\nmodule.exports = { solve };\n',
  c:          '#include <stdio.h>\n\nint main() {\n    // Write your solution here\n    return 0;\n}\n',
  cpp:        '#include <iostream>\nusing namespace std;\n\nint main() {\n    // Write your solution here\n    return 0;\n}\n',
}

export default function Assignment() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [assignment, setAssignment] = useState(null)
  const [loading, setLoading]       = useState(true)
  const [language, setLanguage]     = useState('python')
  const [code, setCode]             = useState(STARTERS.python)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError]           = useState('')
  const fileRef = useRef()

  useEffect(() => {
    api.assignment(id)
      .then(setAssignment)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  function handleLangChange(lang) {
    setLanguage(lang)
    setCode(STARTERS[lang] || '')
  }

  async function handleSubmit() {
    if (!code.trim()) { setError('Code cannot be empty'); return }
    setSubmitting(true)
    setError('')
    try {
      const ext = { python: '.py', java: '.java', javascript: '.js', c: '.c', cpp: '.cpp' }[language] || '.py'
      const blob = new Blob([code], { type: 'text/plain' })
      const file = new File([blob], `solution${ext}`)
      const fd = new FormData()
      fd.append('problem_id', id)
      fd.append('file', file)
      const result = await api.submit(fd)
      navigate(`/evaluation/${result.evaluation_id}`)
    } catch (e) {
      setError(e.message || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return (
    <div className="min-h-screen bg-dark-800 flex items-center justify-center">
      <Loader2 className="h-10 w-10 text-brand-500 animate-spin" />
    </div>
  )

  const diff = (assignment?.difficulty || '').toLowerCase()
  const diffCls = diff.includes('easy') ? 'badge diff-easy' : diff.includes('hard') ? 'badge diff-hard' : 'badge diff-medium'

  return (
    <div className="min-h-screen bg-dark-800 flex flex-col">
      <Topbar />

      <div className="flex-1 flex flex-col lg:flex-row gap-0 overflow-hidden">

        {/* Left: problem */}
        <div className="lg:w-[45%] overflow-y-auto border-r border-white/[0.06] p-5 space-y-4">
          <div>
            <div className="font-mono text-[11px] text-slate-500">{assignment?.id}</div>
            <h1 className="mt-1 text-xl font-extrabold text-white">{assignment?.title}</h1>
            <div className="mt-2 flex flex-wrap gap-2">
              {assignment?.difficulty && <span className={`badge ${diffCls} text-[11px]`}>{assignment.difficulty}</span>}
              {(assignment?.tags || []).map(t => <span key={t} className="badge badge-grey text-[10px]">{t}</span>)}
            </div>
          </div>

          {assignment?.description && (
            <div className="card">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Description</div>
              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">{assignment.description}</p>
            </div>
          )}

          {(assignment?.examples || []).slice(0, 3).map((ex, i) => (
            <div key={i} className="card">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">Example {i + 1}</div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div>
                  <div className="text-[10px] text-slate-500 mb-1">Input</div>
                  <pre className="rounded-lg bg-dark-700 px-3 py-2 text-xs text-slate-200 overflow-x-auto">{ex.input}</pre>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 mb-1">Output</div>
                  <pre className="rounded-lg bg-dark-700 px-3 py-2 text-xs text-slate-200 overflow-x-auto">{ex.output}</pre>
                </div>
              </div>
              {ex.explanation && <p className="mt-2 text-xs text-slate-500">{ex.explanation}</p>}
            </div>
          ))}

          {(assignment?.visible_cases || []).length > 0 && (
            <div className="card">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-3">Visible Test Cases</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] text-slate-500 border-b border-white/[0.06]">
                    <th className="pb-2">#</th><th className="pb-2">Input</th><th className="pb-2">Expected</th>
                  </tr>
                </thead>
                <tbody>
                  {assignment.visible_cases.slice(0, 3).map((c, i) => (
                    <tr key={i} className="border-b border-white/[0.04]">
                      <td className="py-1.5 font-mono text-slate-500">{i + 1}</td>
                      <td className="py-1.5"><code className="text-slate-300">{c.input}</code></td>
                      <td className="py-1.5"><code className="text-slate-300">{c.expected}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: editor */}
        <div className="lg:w-[55%] flex flex-col">
          {/* Editor toolbar */}
          <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/[0.06] bg-dark-700">
            <div className="flex items-center gap-2">
              <label className="text-xs font-semibold text-slate-400">Language</label>
              <select
                value={language}
                onChange={e => handleLangChange(e.target.value)}
                className="rounded-lg bg-dark-600 border border-white/10 px-3 py-1.5 text-sm text-slate-200 outline-none focus:border-brand-500"
              >
                {['python','java','javascript','c','cpp'].map(l => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => setCode(STARTERS[language] || '')} className="btn btn-sm btn-secondary gap-1">
                <RotateCcw className="h-3.5 w-3.5" /> Reset
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !assignment?.active}
                className="btn btn-sm btn-primary gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                {submitting ? 'Submitting…' : 'Submit'}
              </button>
            </div>
          </div>

          {/* Code textarea */}
          <div className="flex-1 overflow-hidden">
            <textarea
              value={code}
              onChange={e => setCode(e.target.value)}
              spellCheck={false}
              className="w-full h-full min-h-[500px] p-4 bg-dark-700 text-slate-100 font-mono text-sm resize-none outline-none border-none placeholder-slate-600"
              placeholder="Write your solution here…"
              onKeyDown={e => {
                if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); handleSubmit() }
                if (e.key === 'Tab') { e.preventDefault(); const s = e.target; const start = s.selectionStart; const end = s.selectionEnd; setCode(c => c.substring(0, start) + '    ' + c.substring(end)); setTimeout(() => { s.selectionStart = s.selectionEnd = start + 4 }, 0) }
              }}
            />
          </div>

          {/* Status bar */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.06] bg-dark-700 text-[11px] text-slate-500">
            <span>Ctrl+Enter to submit</span>
            {error && (
              <div className="flex items-center gap-1.5 text-red-400">
                <AlertTriangle className="h-3.5 w-3.5" /> {error}
              </div>
            )}
            {!assignment?.active && <span className="badge badge-yellow text-[10px]">Not published</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
