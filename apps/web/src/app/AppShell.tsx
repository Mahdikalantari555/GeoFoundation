import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { HealthPill } from './HealthPill'
import { LanguageToggle } from './LanguageToggle'
import { useEvents } from './useEvents'
import { WorkspaceSwitcher } from '@/features/workspace/WorkspaceSwitcher'

export function AppShell() {
  useEvents()
  return (
    <div className="flex h-screen overflow-hidden" data-testid="app-shell">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-gf-border bg-gf-panel px-4 py-2.5">
          <WorkspaceSwitcher />
          <div className="flex items-center gap-3">
            <HealthPill />
            <LanguageToggle />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
