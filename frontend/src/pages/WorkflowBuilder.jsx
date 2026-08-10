import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { api } from '../lib/api'
import Topbar from '../components/Topbar'
import { nodeTypes } from '../components/workflow/CustomNodes'
import NodePalette from '../components/workflow/NodePalette'
import NodeInspector from '../components/workflow/NodeInspector'
import ExecutionPanel from '../components/workflow/ExecutionPanel'
import AIEditPanel from '../components/workflow/AIEditPanel'
import VersionPanel from '../components/workflow/VersionPanel'
import ApprovalBanner from '../components/workflow/ApprovalBanner'
import {
  ArrowLeft, Save, Loader2, AlertCircle, CheckCircle2,
  GitBranch, LayoutGrid, Wand2, Activity, History,
} from 'lucide-react'

// ── Helpers ─────────────────────────────────────────────────────

/** Convert Phase 4 workflow JSON → React Flow nodes + edges */
function wfToFlow(wf) {
  const rfNodes = (wf.nodes || []).map((n, i) => ({
    id:       n.id,
    type:     n.type || 'action',
    position: n._pos || { x: 120 + (i % 4) * 240, y: 80 + Math.floor(i / 4) * 160 },
    data: {
      label:       n.name        || n.id,
      description: n.description || '',
      nodeType:    n.type        || 'action',
      integration: n.action?.integration || '',
      hasRetry:    !!n.retry,
      hasTimeout:  !!n.timeout,
      hasError:    !!n.error_handler,
      status:      n._status || 'idle',
      raw:         n,
    },
  }))

  const rfEdges = (wf.nodes || []).flatMap(n =>
    (n.depends_on || []).map((dep, ei) => ({
      id:           `e-${dep}-${n.id}-${ei}`,
      source:       dep,
      target:       n.id,
      markerEnd:    { type: MarkerType.ArrowClosed, color: '#00b8a3' },
      style:        { stroke: '#00b8a3', strokeWidth: 1.5 },
      animated:     false,
    }))
  )

  return { rfNodes, rfEdges }
}

/** Convert React Flow state back to Phase 4 workflow JSON nodes */
function flowToWfNodes(rfNodes, rfEdges) {
  const deps = {}
  rfEdges.forEach(e => {
    deps[e.target] = deps[e.target] || []
    deps[e.target].push(e.source)
  })

  return rfNodes.map(n => ({
    ...(n.data.raw || {}),
    id:          n.id,
    name:        n.data.label,
    type:        n.data.nodeType,
    description: n.data.description,
    depends_on:  deps[n.id] || [],
    _pos:        n.position,
    _status:     n.data.status,
    ...(n.data.integration ? { action: { ...(n.data.raw?.action || {}), integration: n.data.integration } } : {}),
    ...(n.data.hasRetry    ? { retry:   { max_attempts: 3, backoff_strategy: 'exponential', initial_delay: 'PT1S' } } : { retry: undefined }),
    ...(n.data.hasTimeout  ? { timeout: { duration: 'PT30S' } } : { timeout: undefined }),
  }))
}

/** Validate a new connection — no self-loops, no duplicate edges */
function isValidConnection(connection, edges) {
  if (connection.source === connection.target) return false
  const duplicate = edges.some(
    e => e.source === connection.source && e.target === connection.target
  )
  return !duplicate
}

// ── Inner builder (needs ReactFlowProvider context) ─────────────

function Builder({ workflow, onSave, saving, saveStatus, onNodeStatusChange }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode]  = useState(null)
  const [name,         setName]          = useState(workflow.name || 'Untitled')
  const didInit = useRef(false)

  // Mirror execution status onto canvas nodes
  const handleNodeStatusChange = useCallback((nodeStates) => {
    setNodes(ns => ns.map(n => {
      const ns_ = nodeStates[n.id]
      if (!ns_) return n
      const statusMap = { running: 'running', succeeded: 'success', failed: 'failed',
                          timed_out: 'failed', skipped: 'idle', pending: 'idle' }
      const status = statusMap[ns_.status] || 'idle'
      if (n.data.status === status) return n
      return { ...n, data: { ...n.data, status } }
    }))
    if (onNodeStatusChange) onNodeStatusChange(nodeStates)
  }, [onNodeStatusChange])

  // Initialise from workflow JSON once
  useEffect(() => {
    if (didInit.current) return
    didInit.current = true
    const { rfNodes, rfEdges } = wfToFlow(workflow)
    setNodes(rfNodes)
    setEdges(rfEdges)
  }, [workflow])

  // Keep selectedNode in sync when nodes change
  useEffect(() => {
    if (!selectedNode) return
    const found = nodes.find(n => n.id === selectedNode.id)
    setSelectedNode(found || null)
  }, [nodes])

  const onConnect = useCallback((connection) => {
    if (!isValidConnection(connection, edges)) return
    setEdges(eds => addEdge({
      ...connection,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#00b8a3' },
      style:     { stroke: '#00b8a3', strokeWidth: 1.5 },
    }, eds))
  }, [edges])

  const onNodeClick = useCallback((_, node) => setSelectedNode(node), [])

  const onPaneClick = useCallback(() => setSelectedNode(null), [])

  function handleAddNode(type) {
    const id  = `${type}_${Date.now()}`
    const pos = { x: 200 + Math.random() * 300, y: 150 + Math.random() * 200 }
    const newNode = {
      id,
      type,
      position: pos,
      data: {
        label:       `New ${type}`,
        description: '',
        nodeType:    type,
        integration: '',
        hasRetry:    false,
        hasTimeout:  false,
        hasError:    false,
        status:      'idle',
        raw:         { id, name: `New ${type}`, type, depends_on: [] },
      },
    }
    setNodes(ns => [...ns, newNode])
  }

  function handleNodeChange(nodeId, updates) {
    setNodes(ns => ns.map(n =>
      n.id !== nodeId ? n : { ...n, data: { ...n.data, ...updates } }
    ))
  }

  function handleDeleteNode(nodeId) {
    setNodes(ns => ns.filter(n => n.id !== nodeId))
    setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId))
    setSelectedNode(null)
  }

  function handleSave() {
    const wfNodes = flowToWfNodes(nodes, edges)
    onSave({ name, nodes: wfNodes, edges })
  }

  function handleAutoLayout() {
    // Simple top-down layout by dependency level
    const deps = {}
    edges.forEach(e => { deps[e.target] = deps[e.target] || []; deps[e.target].push(e.source) })
    const levels = {}
    const visited = new Set()
    function assign(id, level) {
      if (visited.has(id)) return
      visited.add(id)
      levels[id] = Math.max(levels[id] || 0, level)
      nodes.filter(n => (deps[n.id] || []).includes(id)).forEach(n => assign(n.id, level + 1))
    }
    nodes.filter(n => !(deps[n.id] || []).length).forEach(n => assign(n.id, 0))
    const buckets = {}
    nodes.forEach(n => { const lv = levels[n.id] || 0; buckets[lv] = buckets[lv] || []; buckets[lv].push(n.id) })
    setNodes(ns => ns.map(n => {
      const lv  = levels[n.id] || 0
      const idx = (buckets[lv] || []).indexOf(n.id)
      const cnt = (buckets[lv] || []).length
      return { ...n, position: { x: 120 + idx * 260 - (cnt - 1) * 130, y: 80 + lv * 160 } }
    }))
  }

  return (
    <div className="flex h-full gap-4">
      {/* Left palette */}
      <NodePalette onAdd={handleAddNode} />

      {/* Canvas */}
      <div className="relative flex-1 rounded-xl border border-white/[0.07] bg-dark-800 overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          deleteKeyCode="Delete"
          proOptions={{ hideAttribution: true }}
          style={{ background: 'transparent' }}
        >
          <Background color="#1a1a2e" gap={20} size={1} />
          <Controls
            showInteractive={false}
            className="!bg-dark-700 !border-white/10 !rounded-xl !shadow-xl [&>button]:!bg-dark-700 [&>button]:!border-white/10 [&>button]:!text-slate-300"
          />
          <MiniMap
            nodeColor={() => '#00b8a3'}
            maskColor="rgba(10,10,15,0.7)"
            className="!bg-dark-700 !border-white/10 !rounded-xl"
          />

          {/* Top-left panel: workflow name + actions */}
          <Panel position="top-left">
            <div className="flex items-center gap-2">
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="input text-sm h-8 py-0 w-52"
                placeholder="Workflow name"
              />
              <button onClick={handleAutoLayout} className="btn btn-secondary btn-sm gap-1.5" title="Auto-layout">
                <LayoutGrid className="h-3.5 w-3.5" /> Layout
              </button>
            </div>
          </Panel>

          {/* Save status */}
          <Panel position="top-right">
            <div className="flex items-center gap-2">
              {saveStatus === 'saved' && (
                <span className="flex items-center gap-1 text-xs text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Saved
                </span>
              )}
              {saveStatus === 'error' && (
                <span className="flex items-center gap-1 text-xs text-red-400">
                  <AlertCircle className="h-3.5 w-3.5" /> Save failed
                </span>
              )}
              <button onClick={handleSave} disabled={saving} className="btn btn-primary btn-sm">
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                Save
              </button>
            </div>
          </Panel>

          {/* Empty hint */}
          {nodes.length === 0 && (
            <Panel position="top-center">
              <div className="rounded-xl border border-dashed border-white/10 bg-dark-700/60 px-6 py-4 text-center text-sm text-slate-400 backdrop-blur">
                <GitBranch className="h-6 w-6 mx-auto mb-2 text-slate-600" />
                Click a node type on the left to add your first node
              </div>
            </Panel>
          )}
        </ReactFlow>
      </div>

      {/* Right inspector */}
      {selectedNode && (
        <NodeInspector
          node={selectedNode}
          onChange={handleNodeChange}
          onDelete={handleDeleteNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  )
}

// Status → React Flow data bridge (used by page wrapper)
export { }

// ── Page wrapper ─────────────────────────────────────────────────

export default function WorkflowBuilder() {
  const { id }   = useParams()
  const navigate = useNavigate()

  const [workflow,    setWorkflow]   = useState(null)
  const [loading,     setLoading]    = useState(true)
  const [error,       setError]      = useState(null)
  const [saving,      setSaving]     = useState(false)
  const [saveStatus,  setSaveStatus] = useState(null)
  const [bottomTab,   setBottomTab]  = useState('ai') // 'execution' | 'ai'
  const [versionOpen, setVersionOpen] = useState(false)

  useEffect(() => { load() }, [id])

  async function load() {
    try {
      setLoading(true)
      const data = await api.workflow(id)
      setWorkflow(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(patch) {
    try {
      setSaving(true)
      setSaveStatus(null)
      await api.updateWorkflow(id, patch)
      setWorkflow(prev => ({ ...prev, ...patch }))
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(null), 3000)
    } catch (e) {
      setSaveStatus('error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-dark-900">
      <Topbar />
      <div className="flex flex-col flex-1 px-4 pt-4 pb-4 gap-4" style={{ minHeight: 0 }}>
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm">
          <Link to="/workflows" className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors">
            <ArrowLeft className="h-4 w-4" /> Workflows
          </Link>
          {workflow && (
            <>
              <span className="text-slate-600">/</span>
              <span className="text-white font-semibold">{workflow.name}</span>
            </>
          )}
        </div>

        {/* States */}
        {loading && (
          <div className="flex flex-1 items-center justify-center text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading workflow…
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" /> {error}
          </div>
        )}

        {/* Canvas + execution panel */}
        {!loading && !error && workflow && (
          <div className="flex flex-col flex-1" style={{ minHeight: 0 }}>

            {/* Approval banner (shows when a run needs human approval) */}
            <ApprovalBanner workflowId={id} />

            {/* History button row */}
            <div className="flex items-center justify-end mb-2 gap-2">
              <button
                onClick={() => setVersionOpen(v => !v)}
                className={`btn btn-secondary btn-sm ${versionOpen ? 'text-brand-400 border-brand-400/40' : ''}`}
              >
                <History className="h-3.5 w-3.5" /> History
              </button>
            </div>

            <div className="flex gap-3 flex-1" style={{ minHeight: 0 }}>
              {/* Canvas */}
              <div className="flex-1 flex flex-col" style={{ minWidth: 0 }}>
                <div style={{ height: 'calc(100vh - 370px)', minHeight: '280px' }}>
                  <ReactFlowProvider>
                    <Builder
                      workflow={workflow}
                      onSave={handleSave}
                      saving={saving}
                      saveStatus={saveStatus}
                    />
                  </ReactFlowProvider>
                </div>

                {/* Bottom panel — tabbed */}
                <div style={{ height: '260px', minHeight: '260px' }} className="rounded-xl overflow-hidden border border-white/[0.07] flex flex-col mt-3">
                  {/* Tab bar */}
                  <div className="flex border-b border-white/[0.06] bg-dark-800">
                    <button
                      onClick={() => setBottomTab('ai')}
                      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-semibold border-b-2 transition-colors
                        ${bottomTab === 'ai'
                          ? 'border-purple-400 text-purple-400'
                          : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                    >
                      <Wand2 className="h-3.5 w-3.5" /> AI Edit
                    </button>
                    <button
                      onClick={() => setBottomTab('execution')}
                      className={`flex items-center gap-1.5 px-4 py-2 text-xs font-semibold border-b-2 transition-colors
                        ${bottomTab === 'execution'
                          ? 'border-brand-400 text-brand-400'
                          : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                    >
                      <Activity className="h-3.5 w-3.5" /> Execution
                    </button>
                  </div>

                  {/* Panel content */}
                  <div className="flex-1 min-h-0 overflow-hidden">
                    {bottomTab === 'execution' && (
                      <ExecutionPanel workflowId={id} />
                    )}
                    {bottomTab === 'ai' && (
                      <AIEditPanel
                        workflowId={id}
                        onApplied={(updatedWf) => { setWorkflow(updatedWf) }}
                      />
                    )}
                  </div>
                </div>
              </div>

              {/* Version history sidebar */}
              {versionOpen && (
                <div className="w-72 flex-shrink-0 rounded-xl border border-white/[0.07] overflow-hidden">
                  <VersionPanel
                    workflowId={id}
                    onRestore={(wf) => { setWorkflow(wf); setVersionOpen(false) }}
                    onClose={() => setVersionOpen(false)}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
