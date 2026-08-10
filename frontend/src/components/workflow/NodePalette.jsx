import { TYPE_META } from './CustomNodes'

const NODE_TYPES = Object.entries(TYPE_META).map(([type, meta]) => ({
  type,
  label: meta.label,
  icon:  meta.icon,
  iconBg: meta.iconBg,
}))

export default function NodePalette({ onAdd }) {
  return (
    <aside className="flex flex-col gap-1 w-48 flex-shrink-0">
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 px-1 mb-1">
        Add Node
      </div>
      {NODE_TYPES.map(({ type, label, icon: Icon, iconBg }) => (
        <button
          key={type}
          onClick={() => onAdd(type)}
          className="flex items-center gap-2.5 rounded-lg border border-white/[0.06] bg-dark-700 px-3 py-2
                     text-left text-xs font-semibold text-slate-300 transition-all
                     hover:border-brand-500/40 hover:bg-dark-600 hover:text-white active:scale-95"
        >
          <span className={`flex h-6 w-6 items-center justify-center rounded-md flex-shrink-0 ${iconBg}`}>
            <Icon className="h-3.5 w-3.5" />
          </span>
          {label}
        </button>
      ))}
    </aside>
  )
}
