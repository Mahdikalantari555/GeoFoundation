import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Activity,
  BookOpen,
  Boxes,
  Bot,
  Map,
  Upload,
  Search,
  MessageSquare,
  Files,
  Database,
  ThumbsUp,
  Gauge,
  Wrench,
  ScrollText,
  MessagesSquare,
  LayoutDashboard,
  Tractor,
} from 'lucide-react'
import { cn } from '@/lib/utils'

type NavItem = {
  to: string
  labelKey: string
  icon: React.ComponentType<{ className?: string }>
}

type NavGroup = { labelKey: string; items: NavItem[] }

const GROUPS: NavGroup[] = [
  {
    labelKey: 'nav.groupWorkspace',
    items: [
      { to: '/', labelKey: 'nav.overview', icon: LayoutDashboard },
      { to: '/settings', labelKey: 'nav.settings', icon: Wrench },
      { to: '/doctor', labelKey: 'nav.doctor', icon: Activity },
    ],
  },
  {
    labelKey: 'nav.groupKnowledge',
    items: [
      { to: '/collections', labelKey: 'nav.collections', icon: Boxes },
      { to: '/ingest', labelKey: 'nav.ingest', icon: Upload },
      { to: '/search', labelKey: 'nav.searchPage', icon: Search },
      { to: '/ask', labelKey: 'nav.ask', icon: MessageSquare },
      { to: '/assets', labelKey: 'nav.assets', icon: Files },
      { to: '/index', labelKey: 'nav.index', icon: Database },
      { to: '/feedback', labelKey: 'nav.feedback', icon: ThumbsUp },
      { to: '/eval', labelKey: 'nav.eval', icon: Gauge },
    ],
  },
  {
    labelKey: 'nav.groupAgent',
    items: [
      { to: '/agent', labelKey: 'nav.agentChat', icon: Bot },
      { to: '/conversations', labelKey: 'nav.conversations', icon: MessagesSquare },
      { to: '/tools', labelKey: 'nav.tools', icon: Wrench },
      { to: '/playbooks', labelKey: 'nav.playbooks', icon: ScrollText },
    ],
  },
  {
    labelKey: 'nav.groupGeo',
    items: [
      { to: '/maps', labelKey: 'nav.maps', icon: Map },
      { to: '/farms', labelKey: 'nav.farms', icon: Tractor },
    ],
  },
]

export function Sidebar() {
  const { t } = useTranslation()

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col overflow-y-auto border-e border-gf-border bg-gf-panel">
      <div className="flex items-center gap-2 px-4 py-4">
        <BookOpen className="size-6 text-gf-accent" />
        <span className="text-lg font-semibold">{t('common.appName')}</span>
      </div>
      <nav className="flex flex-1 flex-col gap-4 px-2 pb-4">
        {GROUPS.map((group) => (
          <div key={group.labelKey}>
            <div className="px-2 pb-1 text-xs font-medium tracking-wide text-gf-muted uppercase">
              {t(group.labelKey)}
            </div>
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
                        isActive
                          ? 'bg-gf-accent-soft font-medium text-gf-accent'
                          : 'text-gf-text hover:bg-gf-accent-soft/60'
                      )
                    }
                  >
                    <item.icon className="size-4 shrink-0" />
                    <span className="truncate">{t(item.labelKey)}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  )
}
