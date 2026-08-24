import { useTranslation } from 'react-i18next'
import { Construction } from 'lucide-react'

export function PlaceholderPage({ milestone }: { milestone?: string }) {
  const { t } = useTranslation()
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <Construction className="size-10 text-gf-accent" />
      <h1 className="text-xl font-semibold">{t('placeholder.title')}</h1>
      <p className="max-w-md text-sm text-gf-muted">{t('placeholder.body')}</p>
      {milestone && (
        <span className="rounded-full border border-gf-border px-2 py-0.5 text-xs text-gf-muted">
          {milestone}
        </span>
      )}
    </div>
  )
}
