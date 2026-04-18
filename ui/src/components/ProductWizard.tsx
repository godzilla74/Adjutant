import { useState } from 'react'
import { api } from '../api'

type Step = 1 | 2 | 3 | 4

interface WsSuggestion {
  id: string
  name: string
  mission: string
  schedule: string
  checked: boolean
  source: 'ai' | 'user'
}
interface ObjSuggestion {
  id: string
  text: string
  progress_target: number | null
  checked: boolean
  source: 'ai' | 'user'
}

interface Props {
  password: string
  onComplete: (productData: { name: string; icon: string; color: string; intent: string; workstreams: WsSuggestion[]; objectives: ObjSuggestion[] }) => void
  onClose: () => void
}

const COLORS = ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444']
const STEPS = ['Your Vision', 'Basics', 'Review Plan', 'Connect Apps']

export default function ProductWizard({ password, onComplete, onClose }: Props) {
  const [step, setStep]     = useState<Step>(1)
  const [intent, setIntent] = useState('')
  const [name, setName]     = useState('')
  const [icon, setIcon]     = useState('🚀')
  const [color, setColor]   = useState(COLORS[0])
  const [loading, setLoading] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)
  const [workstreams, setWorkstreams] = useState<WsSuggestion[]>([])
  const [objectives,  setObjectives]  = useState<ObjSuggestion[]>([])
  const [requiredIntegrations, setRequiredIntegrations] = useState<string[]>([])
  const [addingWs,  setAddingWs]  = useState(false)
  const [addingObj, setAddingObj] = useState(false)
  const [newWsName, setNewWsName] = useState('')
  const [newWsSched, setNewWsSched] = useState('daily')
  const [newObjText, setNewObjText] = useState('')

  const advanceFromStep1 = () => setStep(2)

  const advanceFromStep2 = async () => {
    setLoading(true)
    setPlanError(null)
    try {
      const plan = await api.getWizardPlan(password, intent)
      setWorkstreams(plan.workstreams.map(w => ({ ...w, id: crypto.randomUUID(), checked: true, source: 'ai' as const })))
      setObjectives(plan.objectives.map(o => ({ ...o, id: crypto.randomUUID(), checked: true, source: 'ai' as const })))
      setRequiredIntegrations(plan.required_integrations)
      setStep(3)
    } catch {
      setPlanError('Could not generate a plan. Check your connection and try again.')
    } finally {
      setLoading(false)
    }
  }

  const addUserWs = () => {
    if (!newWsName.trim()) return
    setWorkstreams(ws => [...ws, { id: crypto.randomUUID(), name: newWsName.trim(), mission: '', schedule: newWsSched, checked: true, source: 'user' }])
    setNewWsName('')
    setNewWsSched('daily')
    setAddingWs(false)
  }

  const addUserObj = () => {
    if (!newObjText.trim()) return
    setObjectives(os => [...os, { id: crypto.randomUUID(), text: newObjText.trim(), progress_target: null, checked: true, source: 'user' }])
    setNewObjText('')
    setAddingObj(false)
  }

  const finish = () => {
    onComplete({ name, icon, color, intent, workstreams: workstreams.filter(w => w.checked), objectives: objectives.filter(o => o.checked) })
  }

  const stepNum = (n: number) => (
    <div className={`flex items-center gap-2 ${n < step ? 'text-green-400' : n === step ? 'text-adj-text-primary' : 'text-adj-text-faint'}`}>
      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${n < step ? 'bg-green-800 text-green-400' : n === step ? 'bg-adj-accent text-white' : 'bg-adj-elevated text-adj-text-faint'}`}>
        {n < step ? '✓' : n}
      </span>
      <span className="text-xs">{STEPS[n - 1]}</span>
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-adj-base border border-adj-border rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-adj-surface border-b border-adj-border">
          <span className="text-sm font-bold text-adj-text-primary">Create New Product</span>
          <div className="flex items-center gap-3">
            <span className="text-xs text-adj-text-muted">Step {step} of 4</span>
            <button title="Close" onClick={onClose} className="text-adj-text-muted hover:text-adj-text-primary transition-colors text-lg leading-none">×</button>
          </div>
        </div>

        <div className="flex">
          {/* Step nav */}
          <div className="w-36 bg-adj-panel border-r border-adj-border p-4 flex flex-col gap-3">
            {[1,2,3,4].map(n => <div key={n}>{stepNum(n)}</div>)}
          </div>

          {/* Content */}
          <div className="flex-1 p-6">

            {step === 1 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-1">Let's get started</p>
                <h3 className="text-base font-bold text-adj-text-primary mb-2">What do you want Adjutant to do?</h3>
                <p className="text-xs text-adj-text-muted mb-4">Describe it in plain language — Adjutant will build a plan from your answer.</p>
                <textarea
                  className="w-full bg-adj-panel border border-adj-border rounded-lg px-4 py-3 text-sm text-adj-text-primary placeholder:text-adj-text-faint focus:outline-none focus:border-adj-accent resize-none h-32 transition-colors"
                  placeholder="e.g. I run a small brand. I want Adjutant to manage our Instagram and LinkedIn posts, send a weekly email newsletter, and alert me before anything gets published."
                  value={intent}
                  onChange={e => setIntent(e.target.value)}
                />
                <p className="text-xs text-adj-text-faint mt-2">
                  Not sure what to write?{' '}
                  <button
                    type="button"
                    onClick={() => setIntent("I run a marketing agency. I want Adjutant to manage social media posts across Instagram and LinkedIn, send a weekly email newsletter to clients, monitor competitor blogs, and flag anything that needs my approval before it goes out.")}
                    className="text-adj-accent hover:underline"
                  >
                    See examples →
                  </button>
                </p>
                <div className="flex justify-end mt-4">
                  <button
                    onClick={advanceFromStep1}
                    disabled={!intent.trim()}
                    className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Build My Plan →
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div>
                <h3 className="text-base font-bold text-adj-text-primary mb-5">Name your product</h3>
                <div className="flex gap-3 mb-4">
                  <div className="flex-1">
                    <label htmlFor="product-name" className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Product Name</label>
                    <input
                      id="product-name"
                      className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-adj-text-primary focus:outline-none focus:border-adj-accent transition-colors"
                      value={name}
                      onChange={e => setName(e.target.value)}
                      placeholder="My Brand"
                      autoFocus
                    />
                  </div>
                  <div className="w-20">
                    <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Icon</label>
                    <input maxLength={2} className="w-full bg-adj-panel border border-adj-border rounded-md px-3 py-2 text-sm text-center text-adj-text-primary focus:outline-none focus:border-adj-accent" value={icon} onChange={e => setIcon(e.target.value)} />
                  </div>
                </div>
                <div className="mb-6">
                  <label className="block text-[10px] font-bold uppercase tracking-wider text-adj-text-muted mb-1.5">Color</label>
                  <div className="flex gap-2">
                    {COLORS.map(c => (
                      <button key={c} onClick={() => setColor(c)} className="w-6 h-6 rounded-full transition-transform hover:scale-110" style={{ background: c, outline: color === c ? '2px solid white' : 'none', outlineOffset: '2px' }} />
                    ))}
                  </div>
                </div>
                <div className="flex justify-between">
                  <button onClick={() => setStep(1)} className="text-sm text-adj-text-muted hover:text-adj-text-secondary transition-colors">← Back</button>
                  <button
                    onClick={advanceFromStep2}
                    disabled={!name.trim() || loading}
                    className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors disabled:opacity-40"
                  >
                    {loading ? 'Building plan…' : 'Continue →'}
                  </button>
                </div>
                {planError && <p className="text-xs text-red-400 mt-2 text-right">{planError}</p>}
              </div>
            )}

            {step === 3 && (
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-adj-accent mb-1">Adjutant built this from your vision</p>
                <h3 className="text-base font-bold text-adj-text-primary mb-1">Review and customize your plan</h3>
                <p className="text-xs text-adj-text-muted mb-4">Uncheck anything you don't want. Add your own below each group.</p>

                {/* Workstreams */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-adj-text-faint">⟳ Workstreams</span>
                    <button onClick={() => setAddingWs(true)} className="text-[10px] text-adj-accent border border-dashed border-adj-accent px-2 py-0.5 rounded hover:bg-adj-elevated transition-colors">+ Add workstream</button>
                  </div>
                  {workstreams.map((ws) => (
                    <div key={ws.id} className={`flex items-center gap-2.5 px-3 py-2 rounded-md mb-1.5 border ${ws.checked ? 'bg-adj-panel border-adj-accent-dark' : 'bg-adj-panel border-adj-border opacity-50'}`}>
                      <input type="checkbox" checked={ws.checked} onChange={e => setWorkstreams(wss => wss.map((w) => w.id === ws.id ? { ...w, checked: e.target.checked } : w))} className="accent-adj-accent" />
                      <span className="text-xs text-adj-text-primary flex-1">{ws.name}</span>
                      <span className="text-[9px] text-adj-text-muted">{ws.schedule}</span>
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${ws.source === 'ai' ? 'bg-green-900 text-green-400' : 'bg-amber-900 text-amber-400'}`}>{ws.source === 'ai' ? 'AI' : 'YOU'}</span>
                      {ws.source === 'user' && <button onClick={() => setWorkstreams(wss => wss.filter(w => w.id !== ws.id))} className="text-adj-text-faint hover:text-red-400 text-sm transition-colors">×</button>}
                    </div>
                  ))}
                  {addingWs && (
                    <div className="flex gap-2 mt-1">
                      <input autoFocus className="flex-1 bg-adj-panel border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent" placeholder="What should Adjutant do?" value={newWsName} onChange={e => setNewWsName(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addUserWs(); if (e.key === 'Escape') setAddingWs(false) }} />
                      <select className="bg-adj-panel border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary" value={newWsSched} onChange={e => setNewWsSched(e.target.value)}>
                        <option value="daily">daily</option>
                        <option value="weekly">weekly</option>
                        <option value="monthly">monthly</option>
                        <option value="none">no schedule</option>
                      </select>
                      <button onClick={addUserWs} className="px-3 py-1 bg-adj-accent text-white rounded text-xs font-semibold">Add</button>
                      <button onClick={() => setAddingWs(false)} className="text-adj-text-muted text-sm">✕</button>
                    </div>
                  )}
                </div>

                {/* Objectives */}
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-adj-text-faint">◎ Objectives</span>
                    <button onClick={() => setAddingObj(true)} className="text-[10px] text-adj-accent border border-dashed border-adj-accent px-2 py-0.5 rounded hover:bg-adj-elevated transition-colors">+ Add objective</button>
                  </div>
                  {objectives.map((obj) => (
                    <div key={obj.id} className={`flex items-center gap-2.5 px-3 py-2 rounded-md mb-1.5 border ${obj.checked ? 'bg-adj-panel border-adj-accent-dark' : 'bg-adj-panel border-adj-border opacity-50'}`}>
                      <input type="checkbox" checked={obj.checked} onChange={e => setObjectives(os => os.map((o) => o.id === obj.id ? { ...o, checked: e.target.checked } : o))} className="accent-adj-accent" />
                      <span className="text-xs text-adj-text-primary flex-1">{obj.text}</span>
                      {obj.progress_target != null && <span className="text-[9px] text-adj-text-muted">target: {obj.progress_target}</span>}
                      <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${obj.source === 'ai' ? 'bg-green-900 text-green-400' : 'bg-amber-900 text-amber-400'}`}>{obj.source === 'ai' ? 'AI' : 'YOU'}</span>
                      {obj.source === 'user' && <button onClick={() => setObjectives(os => os.filter(o => o.id !== obj.id))} className="text-adj-text-faint hover:text-red-400 text-sm transition-colors">×</button>}
                    </div>
                  ))}
                  {addingObj && (
                    <div className="flex gap-2 mt-1">
                      <input autoFocus className="flex-1 bg-adj-panel border border-adj-border rounded px-2 py-1 text-xs text-adj-text-primary focus:outline-none focus:border-adj-accent" placeholder="Describe the objective" value={newObjText} onChange={e => setNewObjText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addUserObj(); if (e.key === 'Escape') setAddingObj(false) }} />
                      <button onClick={addUserObj} className="px-3 py-1 bg-adj-accent text-white rounded text-xs font-semibold">Add</button>
                      <button onClick={() => setAddingObj(false)} className="text-adj-text-muted text-sm">✕</button>
                    </div>
                  )}
                </div>

                <div className="flex justify-between">
                  <button onClick={() => setStep(2)} className="text-sm text-adj-text-muted hover:text-adj-text-secondary transition-colors">← Back</button>
                  <button onClick={() => setStep(4)} className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors">Looks good, continue →</button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div>
                <h3 className="text-base font-bold text-adj-text-primary mb-2">Connect apps</h3>
                <p className="text-xs text-adj-text-muted mb-4">
                  {requiredIntegrations.length > 0
                    ? 'Your selected workstreams work best with these integrations. Connect now or skip — you can always do this later in Settings → Connections.'
                    : 'No integrations required. Your product is ready to go!'}
                </p>
                {requiredIntegrations.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    {requiredIntegrations.map(integration => (
                      <span key={integration} className="px-3 py-1 bg-adj-panel border border-adj-border rounded-full text-xs text-adj-text-secondary capitalize">
                        {integration.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-xs text-adj-text-muted mb-6">Connect these in <strong className="text-adj-text-secondary">Settings → Connections</strong> after your product is created.</p>
                <div className="flex justify-between">
                  <button onClick={() => setStep(3)} className="text-sm text-adj-text-muted hover:text-adj-text-secondary transition-colors">← Back</button>
                  <button onClick={finish} className="px-5 py-2 bg-adj-accent text-white rounded-lg text-sm font-semibold hover:bg-adj-accent-dark transition-colors">
                    Create Product 🚀
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  )
}
