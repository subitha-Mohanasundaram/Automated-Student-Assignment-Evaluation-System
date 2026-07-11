import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BrainCircuit, LogIn, UserPlus, AlertCircle } from 'lucide-react'
import { api } from '../lib/api'
import { saveAuth } from '../lib/auth'

export default function Login({ register = false }) {
  const navigate = useNavigate()
  const [form, setForm]     = useState({ username: '', email: '', password: '' })
  const [error, setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const isRegister = register

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = isRegister
        ? await api.register({ username: form.username, email: form.email, password: form.password })
        : await api.login({ username: form.username, password: form.password })
      saveAuth(data)
      navigate('/assignments')
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-dark-800 flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-gradient-to-br from-dark-700 to-dark-800 border-r border-white/[0.06]">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-lg shadow-brand-500/30">
            <BrainCircuit className="h-5 w-5 text-white" />
          </div>
          <span className="text-sm font-extrabold text-white">EduEval <span className="text-brand-400">AI</span></span>
        </Link>

        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1.5 text-[11px] font-semibold text-brand-400 mb-6">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-400" />
            </span>
            Live · Groq LLaMA 3.3-70B
          </div>
          <h2 className="text-4xl font-black text-white leading-tight tracking-tight">
            Code smarter.<br />
            <span className="grad-text">Learn faster.</span>
          </h2>
          <p className="mt-4 text-slate-400 text-sm leading-relaxed max-w-sm">
            Submit code, get instant AI-powered feedback from our ReAct agent —
            not just right or wrong, but exactly why it failed.
          </p>
          <div className="mt-8 space-y-3">
            {[
              'CodeMentor ReAct Agent — 4 tools, autonomous investigation',
              'Sandboxed Docker evaluation — visible, hidden & stress tests',
              'Python · Java · JavaScript · C · C++',
            ].map(item => (
              <div key={item} className="flex items-center gap-2 text-sm text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-500 shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </div>

        <div className="text-xs text-slate-600">EduEval AI · Evaluation Platform</div>
      </div>

      {/* Right: form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              {isRegister ? 'Create account' : 'Welcome back'}
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              {isRegister ? 'Join EduEval AI and start solving.' : 'Sign in to your account.'}
            </p>
          </div>

          {error && (
            <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3">
              <AlertCircle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Username</label>
              <input className="input" type="text" placeholder="alice"
                value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} required />
            </div>
            {isRegister && (
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" placeholder="alice@example.com"
                  value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
              </div>
            )}
            <div>
              <label className="label">Password</label>
              <input className="input" type="password" placeholder="••••••••"
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
            </div>

            <button type="submit" disabled={loading}
              className="btn btn-primary btn-lg w-full justify-center mt-2">
              {loading
                ? 'Please wait…'
                : isRegister
                  ? <><UserPlus className="h-4 w-4" /> Create Account</>
                  : <><LogIn className="h-4 w-4" /> Sign In</>}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            {isRegister
              ? <> Already have an account?{' '}<Link to="/login" className="text-brand-400 hover:underline font-semibold">Sign in</Link></>
              : <> New here?{' '}<Link to="/register" className="text-brand-400 hover:underline font-semibold">Create account</Link></>}
          </p>
        </div>
      </div>
    </div>
  )
}
