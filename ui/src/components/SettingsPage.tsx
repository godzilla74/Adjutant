import { Fragment, useState } from 'react'
import { Product, ProductState, Workstream, Objective } from '../types'
import ProductDropdown from './ProductDropdown'
import OverviewSettings from './settings/OverviewSettings'
import WorkstreamsSettings from './settings/WorkstreamsSettings'
import ObjectivesSettings from './settings/ObjectivesSettings'
import AutonomySettings from './settings/AutonomySettings'
import ConnectionsSettings from './settings/ConnectionsSettings'
import SocialSettings from './settings/SocialSettings'
import AgentModelSettings from './settings/AgentModelSettings'
import GoogleOAuthSettings from './settings/GoogleOAuthSettings'
import IntegrationsSettings from './settings/IntegrationsSettings'
import GlobalMCPSettings from './settings/GlobalMCPSettings'
import ProductMCPSettings from './settings/ProductMCPSettings'
import ImageGenerationSettings from './settings/ImageGenerationSettings'
import TokenUsageSettings from './settings/TokenUsageSettings'
import ProductModelSettings from './settings/ProductModelSettings'
import TagsSettings from './settings/TagsSettings'
export type Tab =
  | 'overview' | 'workstreams' | 'objectives' | 'autonomy'
  | 'connections' | 'social' | 'product-mcp' | 'product-model'
  | 'agent-model' | 'google-oauth' | 'integrations' | 'mcp' | 'image-generation' | 'usage'
  | 'tags'

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

const PRODUCT_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'overview',      label: 'Overview',    icon: '◻' },
  { key: 'workstreams',   label: 'Workstreams', icon: '⟳' },
  { key: 'objectives',    label: 'Objectives',  icon: '◎' },
  { key: 'autonomy',      label: 'Autonomy',    icon: '🛡' },
  { key: 'product-model', label: 'Model',       icon: '🤖' },
]
const INTEGRATION_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'connections', label: 'Connections', icon: '🔗' },
  { key: 'social',      label: 'Social',      icon: '📱' },
  { key: 'product-mcp', label: 'MCP Servers', icon: '⚡' },
]
const GLOBAL_TABS: { key: Tab; label: string; icon: string }[] = [
  { key: 'agent-model',       label: 'Agent Model',       icon: '🤖' },
  { key: 'google-oauth',      label: 'Google OAuth',      icon: '🔑' },
  { key: 'integrations',      label: 'Integrations',      icon: '🔗' },
  { key: 'mcp',               label: 'MCP Servers',       icon: '⚡' },
  { key: 'image-generation',  label: 'Image Generation',  icon: '🖼' },
  { key: 'usage',             label: 'Usage',             icon: '📊' },
  { key: 'tags',              label: 'Tags',              icon: '🏷' },
]

export default function SettingsPage({
  products, activeProductId, productStates, password,
  initialTab = 'overview',
  onClose, onSwitchProduct, onNewProduct, onRefreshData,
  onWorkstreamUpdated, onObjectiveUpdated, onProductUpdated, onProductDeleted,
}: Props) {
  const [tab, setTab] = useState<Tab>(initialTab)
  const [settingsProductId, setSettingsProductId] = useState(activeProductId)

  const activeProduct = products.find(p => p.id === settingsProductId)
  const activeState = productStates[settingsProductId]

  const handleSwitchProduct = (id: string) => {
    setSettingsProductId(id)
    onSwitchProduct(id)
  }

  const navItem = (key: Tab, label: string, icon: string) => (
    <button
      data-testid={`settings-tab-${key}`}
      onClick={() => setTab(key)}
      className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs rounded-sm text-left transition-colors ${
        tab === key
          ? 'text-adj-accent bg-adj-elevated border-r-2 border-adj-accent'
          : 'text-adj-text-muted hover:text-adj-text-secondary hover:bg-adj-elevated'
      }`}
    >
      <span className="w-4 text-center">{icon}</span>
      {label}
    </button>
  )

  const renderContent = () => {
    const common = { password }
    const productCommon = { ...common, productId: settingsProductId }
    switch (tab) {
      case 'overview':      return <OverviewSettings product={activeProduct} onRefresh={() => onRefreshData(settingsProductId)} onProductUpdated={updates => onProductUpdated(settingsProductId, updates)} onProductDeleted={() => onProductDeleted(settingsProductId)} {...common} />
      case 'workstreams':   return <WorkstreamsSettings workstreams={activeState?.workstreams ?? []} onWorkstreamUpdated={onWorkstreamUpdated} onRefresh={() => onRefreshData(settingsProductId)} {...productCommon} />
      case 'objectives':    return <ObjectivesSettings objectives={activeState?.objectives ?? []} onObjectiveUpdated={onObjectiveUpdated} {...productCommon} />
      case 'autonomy':      return <AutonomySettings {...productCommon} />
      case 'product-model': return <ProductModelSettings {...productCommon} />

      case 'connections':   return <ConnectionsSettings {...productCommon} onOpenSettings={tab => { setTab(tab as Tab) }} />
      case 'social':        return <SocialSettings {...common} />
      case 'agent-model':   return <AgentModelSettings {...common} />
      case 'google-oauth':  return <GoogleOAuthSettings {...common} />
      case 'integrations': return <IntegrationsSettings {...common} />
      case 'product-mcp':      return <ProductMCPSettings {...productCommon} />
      case 'mcp':              return <GlobalMCPSettings {...common} />
      case 'image-generation': return <ImageGenerationSettings {...common} />
      case 'usage':            return <TokenUsageSettings {...common} />
      case 'tags':             return <TagsSettings {...common} />
    }
  }

  return (
    <div className="flex flex-col h-full w-full bg-adj-base text-adj-text-primary overflow-hidden">
      {/* Header */}
      <header className="flex items-center gap-3 px-5 h-12 border-b border-adj-border flex-shrink-0 bg-adj-surface">
        <span className="text-sm font-bold text-adj-text-primary">Settings</span>
        <span className="w-px h-4 bg-adj-border" />
        <span className="text-xs text-adj-text-muted">Changes save automatically</span>
        <div className="ml-auto">
          <button
            onClick={onClose}
            className="text-xs text-adj-text-muted hover:text-adj-text-secondary px-3 py-1.5 rounded hover:bg-adj-elevated transition-colors"
          >
            ← Back to workspace
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left nav */}
        <nav className="w-48 bg-adj-panel border-r border-adj-border flex flex-col flex-shrink-0 py-2">
          {/* Product switcher */}
          <div className="px-3 py-2 border-b border-adj-border mb-2">
            <div className="text-[9px] font-bold uppercase tracking-widest text-adj-text-faint mb-2">Editing settings for</div>
            <ProductDropdown
              products={products}
              activeProductId={settingsProductId}
              onSelect={handleSwitchProduct}
              onNewProduct={onNewProduct}
            />
          </div>

          {/* Product tabs */}
          <div className="px-2 mb-1">
            <div className="flex items-center gap-1.5 px-1 py-1 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
              Product
              <span className="px-1 py-0.5 rounded text-[7px] bg-blue-900 text-blue-300 font-bold">this product</span>
            </div>
            {PRODUCT_TABS.map(t => <Fragment key={t.key}>{navItem(t.key, t.label, t.icon)}</Fragment>)}
          </div>

          {/* Integration tabs */}
          <div className="px-2 mb-1 border-t border-adj-border pt-2">
            <div className="flex items-center gap-1.5 px-1 py-1 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
              Integrations
              <span className="px-1 py-0.5 rounded text-[7px] bg-blue-900 text-blue-300 font-bold">this product</span>
            </div>
            {INTEGRATION_TABS.map(t => <Fragment key={t.key}>{navItem(t.key, t.label, t.icon)}</Fragment>)}
          </div>

          {/* Global tabs */}
          <div className="px-2 mt-auto border-t border-adj-border pt-2">
            <div className="flex items-center gap-1.5 px-1 py-1 text-[9px] font-bold uppercase tracking-widest text-adj-text-faint">
              Global
              <span className="px-1 py-0.5 rounded text-[7px] bg-purple-900 text-purple-300 font-bold">all products</span>
            </div>
            {GLOBAL_TABS.map(t => <Fragment key={t.key}>{navItem(t.key, t.label, t.icon)}</Fragment>)}
          </div>
        </nav>

        {/* Content area */}
        <main className="flex-1 overflow-y-auto p-6">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}
