import { useState } from 'react'
import { Product, ProductState, Workstream, Objective } from '../types'
import OverviewSettings from './settings/OverviewSettings'
import ApiKeysSettings from './settings/ApiKeysSettings'
import TokenUsageSettings from './settings/TokenUsageSettings'
import AgentModelSettings from './settings/AgentModelSettings'
import ImageGenerationSettings from './settings/ImageGenerationSettings'
import ProductModelSettings from './settings/ProductModelSettings'
import ConnectionsSettings from './settings/ConnectionsSettings'
import GoogleOAuthSettings from './settings/GoogleOAuthSettings'
import IntegrationsSettings from './settings/IntegrationsSettings'
import SocialSettings from './settings/SocialSettings'
import AutonomySettings from './settings/AutonomySettings'
import ProductMCPSettings from './settings/ProductMCPSettings'
import ObjectivesSettings from './settings/ObjectivesSettings'
import HCASettings from './settings/HCASettings'
import GlobalMCPSettings from './settings/GlobalMCPSettings'
import OrchestratorSettings from './settings/OrchestratorSettings'
import SignalsSettings from './settings/SignalsSettings'
import TagsSettings from './settings/TagsSettings'

export type SettingsItem =
  | 'general-workspace' | 'general-api-keys' | 'general-token-usage'
  | 'models-agent' | 'models-image' | 'models-product'
  | 'connections-all' | 'connections-google' | 'connections-slack-discord' | 'connections-social' | 'connections-telegram'
  | 'products-autonomy' | 'products-mcp' | 'products-objectives'
  | 'system-chief' | 'system-global-mcp' | 'system-orchestrator' | 'system-signals' | 'system-tags'

// Backwards-compatibility alias — includes legacy tab keys from old SettingsPage so App.tsx callers don't break until Task 9
export type Tab = SettingsItem
  | 'overview' | 'workstreams' | 'objectives' | 'autonomy'
  | 'connections' | 'social' | 'product-mcp' | 'product-model'
  | 'agent-model' | 'google-oauth' | 'integrations' | 'mcp' | 'image-generation' | 'usage'
  | 'tags' | 'signals' | 'orchestrator' | 'hca'

interface Group { label: string; items: { key: SettingsItem; label: string }[] }

const GROUPS: Group[] = [
  { label: 'Connections', items: [
    { key: 'connections-all',           label: 'All connections' },
    { key: 'connections-google',        label: 'Google' },
    { key: 'connections-slack-discord', label: 'Slack / Discord' },
    { key: 'connections-social',        label: 'Social' },
    { key: 'connections-telegram',      label: 'Telegram' },
  ]},
  { label: 'General', items: [
    { key: 'general-api-keys',    label: 'API Keys' },
    { key: 'general-token-usage', label: 'Token Usage' },
    { key: 'general-workspace',   label: 'Workspace' },
  ]},
  { label: 'Models', items: [
    { key: 'models-agent',   label: 'Agent default' },
    { key: 'models-image',   label: 'Image generation' },
    { key: 'models-product', label: 'Per-product' },
  ]},
  { label: 'Products', items: [
    { key: 'products-autonomy',   label: 'Autonomy' },
    { key: 'products-mcp',        label: 'MCP servers' },
    { key: 'products-objectives', label: 'Objectives' },
  ]},
  { label: 'System', items: [
    { key: 'system-chief',        label: 'Chief Adjutant' },
    { key: 'system-global-mcp',   label: 'Global MCP' },
    { key: 'system-orchestrator', label: 'Orchestrator' },
    { key: 'system-signals',      label: 'Signals' },
    { key: 'system-tags',         label: 'Tags' },
  ]},
]

interface Props {
  products: Product[]
  activeProductId: string
  productStates: Record<string, ProductState>
  password: string
  initialTab?: Tab
  onClose: () => void
  onSwitchProduct: (id: string) => void
  onNewProduct: () => void
  onRefreshData: (productId: string) => void
  onWorkstreamUpdated: (wsId: number, patch: Partial<Workstream>) => void
  onObjectiveUpdated: (objId: number, patch: Partial<Objective>) => void
  onProductUpdated: (productId: string, updates: { name?: string; icon_label?: string; color?: string }) => void
  onProductDeleted: (productId: string) => void
}

// Map legacy tab keys to new SettingsItem equivalents
function resolveInitialTab(tab: Tab | undefined): SettingsItem {
  switch (tab as string) {
    case 'overview':         return 'general-workspace'
    case 'workstreams':      return 'general-workspace'
    case 'objectives':       return 'products-objectives'
    case 'autonomy':         return 'products-autonomy'
    case 'connections':      return 'connections-all'
    case 'social':           return 'connections-social'
    case 'product-mcp':      return 'products-mcp'
    case 'product-model':    return 'models-product'
    case 'agent-model':      return 'models-agent'
    case 'google-oauth':     return 'connections-google'
    case 'integrations':     return 'connections-slack-discord'
    case 'mcp':              return 'system-global-mcp'
    case 'image-generation': return 'models-image'
    case 'usage':            return 'general-token-usage'
    case 'tags':             return 'system-tags'
    case 'signals':          return 'system-signals'
    case 'orchestrator':     return 'system-orchestrator'
    case 'hca':              return 'system-chief'
    default:                 return (tab as SettingsItem) ?? 'general-workspace'
  }
}

export default function SettingsPage({
  products, activeProductId, productStates, password,
  initialTab,
  onClose: _onClose, onSwitchProduct: _onSwitchProduct, onNewProduct: _onNewProduct, onRefreshData,
  onWorkstreamUpdated: _onWorkstreamUpdated, onObjectiveUpdated, onProductUpdated, onProductDeleted,
}: Props) {
  const [active, setActive] = useState<SettingsItem>(() => resolveInitialTab(initialTab))
  const activeProduct = products.find(p => p.id === activeProductId)
  const activeState   = productStates[activeProductId]

  const renderContent = () => {
    switch (active) {
      case 'general-workspace':    return <OverviewSettings product={activeProduct} password={password} onRefresh={() => onRefreshData(activeProductId)} onProductUpdated={updates => onProductUpdated(activeProductId, updates)} onProductDeleted={() => onProductDeleted(activeProductId)} />
      case 'general-api-keys':     return <ApiKeysSettings password={password} />
      case 'general-token-usage':  return <TokenUsageSettings password={password} />
      case 'models-agent':         return <AgentModelSettings password={password} />
      case 'models-image':         return <ImageGenerationSettings password={password} />
      case 'models-product':       return <ProductModelSettings password={password} productId={activeProductId} />
      case 'connections-all':      return <ConnectionsSettings password={password} productId={activeProductId} />
      case 'connections-google':   return <GoogleOAuthSettings password={password} />
      case 'connections-slack-discord': return <IntegrationsSettings password={password} />
      case 'connections-social':   return <SocialSettings password={password} />
      case 'connections-telegram': return <IntegrationsSettings password={password} />
      case 'products-autonomy':    return <AutonomySettings password={password} productId={activeProductId} />
      case 'products-mcp':         return <ProductMCPSettings password={password} productId={activeProductId} />
      case 'products-objectives':  return activeState ? <ObjectivesSettings productId={activeProductId} objectives={activeState.objectives} password={password} onObjectiveUpdated={onObjectiveUpdated} /> : null
      case 'system-chief':         return <HCASettings password={password} />
      case 'system-global-mcp':    return <GlobalMCPSettings password={password} />
      case 'system-orchestrator':  return <OrchestratorSettings password={password} productId={activeProductId} />
      case 'system-signals':       return <SignalsSettings password={password} productId={activeProductId} />
      case 'system-tags':          return <TagsSettings password={password} />
      default:                     return null
    }
  }

  return (
    <div className="flex flex-1 overflow-hidden bg-adj-base">

      {/* Grouped sidebar */}
      <div className="w-44 bg-adj-surface border-r border-adj-border overflow-y-auto flex-shrink-0 py-3">
        {GROUPS.map(group => (
          <div key={group.label} className="mb-1 px-3">
            <div className="text-[9px] text-adj-text-faint uppercase tracking-widest px-1 mb-1">{group.label}</div>
            {group.items.map(item => (
              <button
                key={item.key}
                onClick={() => setActive(item.key)}
                className={`w-full text-left text-[11px] rounded-md px-2 py-1.5 mb-0.5 transition-colors ${
                  active === item.key
                    ? 'bg-adj-elevated border border-adj-border text-adj-text-primary'
                    : 'text-adj-text-faint hover:text-adj-text-secondary hover:bg-adj-elevated/50'
                }`}
              >
                {item.label}
              </button>
            ))}
            <div className="h-px bg-adj-border my-2" />
          </div>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {renderContent()}
      </div>
    </div>
  )
}
