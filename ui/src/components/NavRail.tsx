export type Section = 'overview' | 'products' | 'chief' | 'settings'

interface Props {
  section: Section
  reviewBadgeCount: number
  agentInitial: string
  onNavigate: (s: Section) => void
}

const NAV_ITEMS: { section: Section; title: string; icon: string }[] = [
  { section: 'overview',  title: 'Overview',  icon: '⊞' },
  { section: 'products',  title: 'Products',  icon: '◎' },
  { section: 'chief',     title: 'Chief',     icon: '✦' },
]

export default function NavRail({ section, reviewBadgeCount, agentInitial, onNavigate }: Props) {
  return (
    <div className="w-14 bg-adj-base border-r border-adj-border flex flex-col items-center py-3 gap-1 flex-shrink-0">
      {/* Logo */}
      <div className="w-8 h-8 rounded-lg bg-adj-accent text-white text-sm font-bold flex items-center justify-center mb-3 flex-shrink-0">
        {agentInitial}
      </div>

      {/* Main nav items */}
      {NAV_ITEMS.map(item => (
        <div key={item.section} className="flex flex-col items-center gap-0.5 w-full px-1 mb-1">
          <button
            type="button"
            title={item.title}
            onClick={() => onNavigate(item.section)}
            className={`w-10 h-10 rounded-lg flex items-center justify-center text-base transition-colors relative ${
              section === item.section
                ? 'bg-adj-accent/20 border border-adj-accent/50 text-adj-accent'
                : 'text-adj-text-faint hover:text-adj-text-secondary hover:bg-adj-elevated'
            }`}
          >
            {item.icon}
            {item.section === 'chief' && reviewBadgeCount > 0 && (
              <span className="absolute top-1 right-1 bg-amber-500 text-white text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold leading-none">
                {reviewBadgeCount > 9 ? '9+' : reviewBadgeCount}
              </span>
            )}
          </button>
          <span className="text-[8px] text-adj-text-faint uppercase tracking-wide">{item.title}</span>
        </div>
      ))}

      {/* Settings pinned to bottom */}
      <div className="flex flex-col items-center gap-0.5 w-full px-1 mt-auto">
        <button
          type="button"
          title="Settings"
          onClick={() => onNavigate('settings')}
          className={`w-10 h-10 rounded-lg flex items-center justify-center text-base transition-colors ${
            section === 'settings'
              ? 'bg-adj-accent/20 border border-adj-accent/50 text-adj-accent'
              : 'text-adj-text-faint hover:text-adj-text-secondary hover:bg-adj-elevated'
          }`}
        >
          ⚙
        </button>
        <span className="text-[8px] text-adj-text-faint uppercase tracking-wide">Settings</span>
      </div>
    </div>
  )
}
