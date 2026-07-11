import { Bot, Target, MapPin, Bug, Shield, Lightbulb, Terminal, ChevronDown } from 'lucide-react'
import { useState } from 'react'

export default function AIFeedback({ feedback }) {
  const [traceOpen, setTraceOpen] = useState(false)
  if (!feedback?.explanation) return null

  const conf = Math.round((feedback.confidence || 0) * 100)
  const confClass = conf >= 80 ? 'badge-green' : conf >= 50 ? 'badge-yellow' : 'badge-grey'

  return (
    <div className="card relative overflow-hidden border-brand-500/20">
      {/* Top accent */}
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-brand-500 via-accent-500 to-brand-500" />

      {/* Header */}
      <div className="flex items-start justify-between gap-3 pt-1 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 shadow-md shadow-brand-500/25 shrink-0">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="text-base font-extrabold text-white tracking-tight">CodeMentor AI</div>
            <div className="text-[11px] text-brand-400 font-semibold">ReAct Agent · LLaMA 3.3-70B · Groq</div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {feedback.confidence != null && (
            <span className={`badge ${confClass} gap-1`}>
              <Target className="h-3 w-3" /> {conf}% confidence
            </span>
          )}
          {feedback.reasoning_turns && (
            <span className="badge badge-blue gap-1">
              {feedback.reasoning_turns} turn{feedback.reasoning_turns !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {/* Sections */}
      <div className="mt-5 space-y-3">
        {/* What went wrong */}
        <div className="rounded-xl border border-white/[0.07] bg-dark-600 px-4 py-3.5">
          <div className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-2">What went wrong</div>
          <p className="text-sm text-slate-200 leading-relaxed">{feedback.explanation}</p>
        </div>

        {/* Likely cause + Root cause */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {feedback.likely_cause && (
            <div className="rounded-xl border border-accent-500/20 bg-accent-500/[0.07] px-4 py-3">
              <div className="flex items-center gap-1.5 mb-2">
                <MapPin className="h-3.5 w-3.5 text-accent-500" />
                <div className="text-[10px] font-black uppercase tracking-widest text-accent-500">Likely Cause</div>
              </div>
              <code className="text-[12px] text-accent-400 leading-relaxed block">{feedback.likely_cause}</code>
            </div>
          )}
          {feedback.root_cause && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/[0.07] px-4 py-3">
              <div className="flex items-center gap-1.5 mb-2">
                <Bug className="h-3.5 w-3.5 text-red-400" />
                <div className="text-[10px] font-black uppercase tracking-widest text-red-400">Root Cause</div>
              </div>
              <code className="text-[12px] text-red-300 leading-relaxed block">{feedback.root_cause}</code>
            </div>
          )}
        </div>

        {/* Why hidden fail */}
        {feedback.why_hidden_fail && (
          <div className="rounded-xl border border-purple-500/20 bg-purple-500/[0.07] px-4 py-3">
            <div className="flex items-center gap-1.5 mb-2">
              <Shield className="h-3.5 w-3.5 text-purple-400" />
              <div className="text-[10px] font-black uppercase tracking-widest text-purple-400">Why Hidden Tests Fail</div>
            </div>
            <p className="text-sm text-purple-200 leading-relaxed">{feedback.why_hidden_fail}</p>
          </div>
        )}

        {/* Hint */}
        <div className="rounded-xl border-2 border-brand-500/30 bg-brand-500/[0.08] px-4 py-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-500 shadow-sm shadow-brand-500/30">
              <Lightbulb className="h-3.5 w-3.5 text-white" />
            </div>
            <div className="text-[10px] font-black uppercase tracking-widest text-brand-400">Hint</div>
            <span className="text-[10px] text-slate-500">(not the solution)</span>
          </div>
          <p className="text-sm font-semibold text-brand-200 leading-relaxed">{feedback.hint}</p>
        </div>
      </div>

      {/* Agent trace */}
      {feedback.tools_used?.length > 0 && (
        <div className="mt-4">
          <button
            onClick={() => setTraceOpen(v => !v)}
            className="flex items-center gap-2 text-[12px] font-semibold text-slate-500 hover:text-slate-300 transition"
          >
            <Terminal className="h-3.5 w-3.5" />
            Agent investigation trace
            <ChevronDown className={`h-3.5 w-3.5 ml-auto transition-transform ${traceOpen ? 'rotate-180' : ''}`} />
          </button>
          {traceOpen && (
            <div className="mt-3 flex flex-wrap gap-2">
              {feedback.tools_used.map((t, i) => (
                <div key={i} className="flex items-center gap-1.5 rounded-full border border-brand-500/20 bg-brand-500/5 px-3 py-1.5">
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-brand-500/20 text-[9px] font-black text-brand-400">{i + 1}</span>
                  <code className="text-[11px] font-semibold text-slate-300">{t}</code>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
