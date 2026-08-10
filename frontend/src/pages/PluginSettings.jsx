import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import {
  Settings2, Save, Loader2, CheckCircle2, AlertCircle,
  Eye, EyeOff, ChevronDown, ChevronUp,
} from 'lucide-react'

const PLUGIN_META = {
  email:    { name: 'Email (SMTP)',   icon: '✉️',  secrets: ['SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD'] },
  slack:    { name: 'Slack',          icon: '💬',  secrets: ['SLACK_BOT_TOKEN'] },
  github:   { name: 'GitHub',         icon: '🐙',  secrets: ['GITHUB_TOKEN'] },
  openai:   { name: 'OpenAI',         icon: '🤖',  secrets: ['OPENAI_API_KEY'] },
  google:   { name: 'Google',         icon: '🔵',  secrets: ['GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REFRESH_TOKEN'] },
  weather:  { name: 'OpenWeatherMap', icon: '🌤️',  secrets: ['OPENWEATHER_API_KEY'] },
  currency: { name: 'Currency API',   icon: '💱',  secrets: ['CURRENCY_API_KEY'] },
  rest_api: { name: 'REST API',       icon: '🌐',  secrets: ['PLUGIN_API_KEY','PLUGIN_BEARER_TOKEN'] },
}

function PluginSection({ pluginId, meta, existingConfig, onSave, saving }) {
  const [open,    setOpen]    = useState(false)
  const [secrets, setSecrets] = useState({})
  const [show,    setShow]    = useState({})

  function handleChange(key, val) {
    setSecrets(s => ({ ...s, [key]: val }))
  }

  function handleSave() {
    onSave(pluginId, { secrets })
  }

  return (
    <div className="rounded-xl border border-white/[0.07] overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-3 w-full px-4 py-3 hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-lg">{meta.icon}</span>
        <span className="font-semibold text-white flex-1 text-left">{meta.name}</span>
        {existingConfig?.has_secrets && (
          <span className="badge badge-green text-[9px]">Configured</span>
        )}
        {open ? <ChevronUp className="h-4 w-4 text-slate-500" /> : <ChevronDown className="h-4 w-4 text-slate-500" />}
      </button>

      {open && (
        <div className="px-4 pb-4 pt-2 border-t border-white/[0.05] space-y-3">
          {meta.secrets.map(key => (
            <div key={key}>
              <label className="label text-[10px]">{key}</label>
              <div className="flex gap-2">
                <input
                  type={show[key] ? 'text' : 'password'}
                  value={secrets[key] || ''}
                  onChange={e => handleChange(key, e.target.value)}
                  placeholder={existingConfig?.has_secrets ? '••••••••' : `Enter ${key}`}
                  className="input flex-1 text-xs font-mono"
                />
                <button
                  onClick={() => setShow(s => ({ ...s, [key]: !s[key] }))}
                  className="btn btn-secondary btn-sm px-2"
                >
                  {show[key] ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>
          ))}
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn-primary btn-sm w-full"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
            Save Credentials
          </button>
        </div>
      )}
    </div>
  )
}

export default function PluginSettings() {
  const [configs,  setConfigs]  = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [saving,   setSaving]   = useState(null)
  const [success,  setSuccess]  = useState(null)
  const [error,    setError]    = useState(null)

  useEffect(() => { loadConfigs() }, [])

  async function loadConfigs() {
    setLoading(true)
    try {
      const res = await api.pluginConfigs()
      setConfigs(res.configs || {})
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(pluginId, cfg) {
    setSaving(pluginId)
    setError(null)
    setSuccess(null)
    try {
      await api.savePluginConfigs({ [pluginId]: cfg })
      setSuccess(pluginId)
      await loadConfigs()
      setTimeout(() => setSuccess(null), 2500)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="max-w-xl mx-auto py-8 px-4">
      <div className="flex items-center gap-3 mb-6">
        <Settings2 className="h-6 w-6 text-brand-400" />
        <div>
          <h1 className="text-xl font-bold text-white">Plugin Settings</h1>
          <p className="text-sm text-slate-400">Configure API keys and credentials for each integration</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs text-red-400 mb-4">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" /> {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400 mb-4">
          <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0" /> {PLUGIN_META[success]?.name} credentials saved
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 text-brand-400 animate-spin" />
        </div>
      ) : (
        <div className="space-y-3">
          {Object.entries(PLUGIN_META).map(([id, meta]) => (
            <PluginSection
              key={id}
              pluginId={id}
              meta={meta}
              existingConfig={configs?.[id]}
              onSave={handleSave}
              saving={saving === id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
