// ui/src/types.ts

export interface Product {
  id: string
  name: string
  icon_label: string
  color: string
}

export interface ProductConfig extends Product {
  brand_voice?:     string | null
  tone?:            string | null
  writing_style?:   string | null
  target_audience?: string | null
  social_handles?:  string | null
  hashtags?:        string | null
  brand_notes?:     string | null
}

export interface Workstream {
  id: number
  name: string
  status: 'running' | 'warn' | 'paused'
  display_order: number
  mission?: string | null
  schedule?: string | null
  last_run_at?: string | null
  next_run_at?: string | null
}

export interface Objective {
  id: number
  text: string
  progress_current: number
  progress_target: number | null
  display_order: number
  autonomous?: number          // 0 | 1
  session_id?: string | null
  next_run_at?: string | null
  last_run_at?: string | null
  blocked_by_review_id?: number | null
}

export type AgentType = 'research' | 'general' | 'email' | 'content' | 'social'

export interface ActivityEvent {
  id: number
  agent_type: AgentType
  headline: string
  rationale: string
  status: 'running' | 'done' | 'needs_review'
  output_preview?: string | null
  summary?: string | null
  created_at: string
}

export interface ReviewItem {
  id: number
  title: string
  description: string
  risk_label: string
  status: 'pending' | 'approved' | 'skipped'
  created_at: string
  action_type?: string | null
  auto_approve_at?: string | null
  scheduled_for?: string | null
}

export interface ProductState {
  workstreams:           Workstream[]
  objectives:            Objective[]
  events:                ActivityEvent[]
  review_items:          ReviewItem[]
  sessions:              Session[]
  activeSessionId:       string | null
  launch_wizard_active?: number
}

export interface DirectiveItem {
  id: string
  content: string
}

// WebSocket messages from server
export type ServerMessage =
  | { type: 'auth_ok' }
  | { type: 'auth_fail'; reason: string }
  | { type: 'init'; products: Product[] }
  | { type: 'product_data'; product_id: string; sessions: Session[]; active_session_id: string | null; workstreams: Workstream[]; objectives: Objective[]; events: ActivityEvent[]; review_items: ReviewItem[]; chat_history?: Array<{ type: 'directive' | 'agent'; content: string; ts: string }>; launch_wizard_active?: number }
  | { type: 'session_created'; session: Session }
  | { type: 'session_switched'; session_id: string; chat_history: Array<{ type: 'directive' | 'agent'; content: string; ts: string }> }
  | { type: 'session_renamed'; session_id: string; name: string }
  | { type: 'session_deleted'; session_id: string; next_session_id: string }
  | { type: 'directive_echo'; product_id: string; content: string; ts: string }
  | { type: 'activity_started'; product_id: string; id: number; agent_type: AgentType; headline: string; rationale: string; ts: string }
  | { type: 'activity_done'; product_id: string; id: number; summary: string; ts: string }
  | { type: 'review_item_added'; product_id: string; item: ReviewItem }
  | { type: 'review_resolved'; review_item_id: number; action: string }
  | { type: 'review_item_updated'; product_id: string; item: ReviewItem }
  | { type: 'autonomy_config'; product_id: string; master_tier: string | null; master_window_minutes: number | null; action_overrides: Array<{ action_type: string; tier: string; window_minutes: number | null }> }
  | { type: 'agent_token'; product_id: string; content: string }
  | { type: 'agent_done'; product_id: string; content: string; ts: string }
  | { type: 'queue_update'; product_id: string; current: DirectiveItem | null; queued: DirectiveItem[] }
  | { type: 'wizard_progress'; product_id: string; message: string }
  | { type: 'launch_complete'; product_id: string; summary: string }
  | { type: 'launch_started'; product_id: string }

export interface DirectiveHistoryItem {
  id: number
  content: string
  created_at: string
}

export interface ProductOverview {
  id: string
  name: string
  icon_label: string
  color: string
  running_ws: number
  warn_ws: number
  paused_ws: number
  pending_reviews: number
  running_agents: number
}

export interface Session {
  id: string
  name: string
  product_id: string | null
  created_at: string
}
