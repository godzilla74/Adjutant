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
}

export interface ProductState {
  workstreams:     Workstream[]
  objectives:      Objective[]
  events:          ActivityEvent[]
  review_items:    ReviewItem[]
  sessions:        Session[]
  activeSessionId: string | null
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
  | { type: 'product_data'; product_id: string; sessions: Session[]; active_session_id: string | null; workstreams: Workstream[]; objectives: Objective[]; events: ActivityEvent[]; review_items: ReviewItem[]; chat_history?: Array<{ type: 'directive' | 'agent'; content: string; ts: string }> }
  | { type: 'session_created'; session: Session }
  | { type: 'session_switched'; session_id: string; chat_history: Array<{ type: 'directive' | 'agent'; content: string; ts: string }> }
  | { type: 'session_renamed'; session_id: string; name: string }
  | { type: 'session_deleted'; session_id: string; next_session_id: string }
  | { type: 'directive_echo'; product_id: string; content: string; ts: string }
  | { type: 'activity_started'; product_id: string; id: number; agent_type: AgentType; headline: string; rationale: string; ts: string }
  | { type: 'activity_done'; product_id: string; id: number; summary: string; ts: string }
  | { type: 'review_item_added'; product_id: string; item: ReviewItem }
  | { type: 'review_resolved'; review_item_id: number; action: string }
  | { type: 'agent_token'; product_id: string; content: string }
  | { type: 'agent_done'; product_id: string; content: string; ts: string }
  | { type: 'queue_update'; product_id: string; current: DirectiveItem | null; queued: DirectiveItem[] }

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
