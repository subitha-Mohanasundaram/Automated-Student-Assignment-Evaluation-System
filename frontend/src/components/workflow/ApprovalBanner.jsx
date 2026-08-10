import { useState, useEffect } from 'react'
import { api } from '../../lib/api'
import { Bell, CheckCircle2, XCircle, Loader2, User } from 'lucide-react'

/**
 * ApprovalBanner
 * =============
 * Polls the most recent run for the workflow.
 * If the latest run has a node in status "awaiting_approval",
 * shows a banner with Approve / Reject buttons.
 */
export default function ApprovalBanner({ workflowId }) {
  const [approvalRun, setApprovalRun] = useState(null) // { run_id, node_id, node_name }
  const [acting,      setActing]      = useState(null)  // 'approve' | 'reject'
  const [comment,     setComment]     = useState('')
  const [done,        setDone]        = useState(false)

  useEffect(() => {
    if (!workflowId) return
    const iv = setInterval(checkApprovals, 5000)
    checkApprovals()
    return () => clearInterval(iv)
  }, [workflowId])

  async function checkApprovals() {
    if (done) return
    try {
      const res = await api.workflowRuns(workflowId)
      const runs = res.runs || []
      if (runs.length === 0) return
      const latest = runs[0]
      const runDetail = await api.runStatus(latest.run_id)
      const awaitingNode = Object.values(runDetail.node_states || {})
        .find(ns => ns.status === 'awaiting_approval')
      if (awaitingNode) {
        setApprovalRun({ run_id: latest.run_id, node_id: awaitingNode.node_id, node_name: awaitingNode.node_id })
        setDone(false)
      } else {
        setApprovalRun(null)
      }
    } catch {
      // silently ignore
    }
  }

  async function handleDecision(approved) {
    if (!approvalRun) return
    setActing(approved ? 'approve' : 'reject')
    try {
      if (approved) {
        await api.approveRun(approvalRun.run_id, { comment })
      } else {
        await api.rejectRun(approvalRun.run_id, { comment })
      }
      setDone(true)
      setApprovalRun(null)
    } catch (e) {
      console.error(e)
    } finally {
      setActing(null)
    }
  }

  if (!approvalRun) return null

  return (
    <div className="mb-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-start gap-3">
      <Bell className="h-4 w-4 text-amber-400 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-amber-300 text-sm">Human Approval Required</div>
        <div className="text-xs text-amber-200/70 mt-0.5">
          Node <code className="font-mono text-amber-300">{approvalRun.node_name}</code> is waiting for approval
          in run <code className="font-mono text-amber-300">{approvalRun.run_id.slice(0, 12)}…</code>
        </div>
        <div className="flex items-center gap-2 mt-2">
          <input
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="Optional comment…"
            className="input text-xs flex-1 py-1"
          />
          <button
            onClick={() => handleDecision(true)}
            disabled={!!acting}
            className="btn btn-sm bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-500 flex items-center gap-1"
          >
            {acting === 'approve' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            Approve
          </button>
          <button
            onClick={() => handleDecision(false)}
            disabled={!!acting}
            className="btn btn-sm bg-red-700 hover:bg-red-600 text-white border-red-600 flex items-center gap-1"
          >
            {acting === 'reject' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
            Reject
          </button>
        </div>
      </div>
    </div>
  )
}
