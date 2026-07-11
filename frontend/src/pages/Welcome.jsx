import { Link } from 'react-router-dom'
import { BrainCircuit, Bot, ShieldCheck, Code2, Trophy, ArrowRight, Zap } from 'lucide-react'

export default function Welcome() {
  return (
    <div className="min-h-screen bg-dark-800 flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-lg shadow-brand-500/30">
            <BrainCircuit className="h-5 w-5 text-white" />
          </div>
          <span className="text-sm font-extrabold text-white">EduEval <span className="text-brand-400">AI</span></span>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/login"    className="btn btn-sm btn-secondary">Login</Link>
          <Link to="/register" className="btn btn-sm btn-primary">Get Started</Link>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-20 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-4 py-1.5 text-xs font-semibold text-brand-400 mb-8">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-400" />
          </span>
          Powered by Groq · LLaMA 3.3-70B · ReAct Agent
        </div>

        <h1 className="text-5xl md:text-7xl font-black tracking-tight text-white leading-tight max-w-4xl">
          Code. Submit.{' '}
          <span className="grad-text">Get AI Feedback.</span>
        </h1>
        <p className="mt-6 text-lg text-slate-400 max-w-2xl leading-relaxed">
          Submit your code and our AI agent autonomously investigates why it failed —
          not just <em className="text-slate-200 not-italic">what</em> went wrong, but
          exactly <em className="text-brand-400 not-italic font-semibold">why</em> and how to fix it.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
          <Link to="/register" className="btn btn-primary btn-lg gap-2">
            Start Solving <ArrowRight className="h-5 w-5" />
          </Link>
          <Link to="/login" className="btn btn-secondary btn-lg">
            Sign In
          </Link>
        </div>

        {/* Stats */}
        <div className="mt-16 grid grid-cols-2 gap-4 sm:grid-cols-4 max-w-2xl w-full">
          {[
            { label: 'Languages', value: '5' },
            { label: 'AI Tools', value: '4' },
            { label: 'Agent Turns', value: '≤6' },
            { label: 'Avg Response', value: '<3s' },
          ].map(s => (
            <div key={s.label} className="card text-center">
              <div className="text-3xl font-black text-brand-400 font-mono">{s.value}</div>
              <div className="text-xs text-slate-500 mt-1 font-semibold uppercase tracking-wider">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Features */}
        <div className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 max-w-5xl w-full">
          {[
            { icon: Bot,         color: 'brand', title: 'CodeMentor Agent',     desc: 'ReAct agent calls 4 tools autonomously to investigate failures' },
            { icon: ShieldCheck, color: 'emerald', title: 'Sandboxed Tests',    desc: 'Docker container with --network none for safe execution' },
            { icon: Code2,       color: 'blue',  title: '5 Languages',           desc: 'Python, Java, JavaScript, C, C++ with Monaco editor' },
            { icon: Trophy,      color: 'accent', title: 'Leaderboards',         desc: 'Real-time rankings and class analytics' },
          ].map(({ icon: Icon, color, title, desc }) => (
            <div key={title} className="card card-hover text-left">
              <div className={`flex h-10 w-10 items-center justify-center rounded-xl mb-4
                ${color === 'brand'   ? 'bg-brand-500/15'   : ''}
                ${color === 'emerald' ? 'bg-emerald-500/15' : ''}
                ${color === 'blue'    ? 'bg-blue-500/15'    : ''}
                ${color === 'accent'  ? 'bg-accent-500/15'  : ''}`}>
                <Icon className={`h-5 w-5
                  ${color === 'brand'   ? 'text-brand-400'   : ''}
                  ${color === 'emerald' ? 'text-emerald-400' : ''}
                  ${color === 'blue'    ? 'text-blue-400'    : ''}
                  ${color === 'accent'  ? 'text-accent-500'  : ''}`} />
              </div>
              <div className="text-sm font-bold text-white">{title}</div>
              <div className="mt-1 text-xs text-slate-400 leading-relaxed">{desc}</div>
            </div>
          ))}
        </div>
      </main>

      <footer className="text-center py-6 text-xs text-slate-600 border-t border-white/[0.04]">
        EduEval AI · Built with FastAPI + React + Groq
      </footer>
    </div>
  )
}
