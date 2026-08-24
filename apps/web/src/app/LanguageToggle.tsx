import { useTranslation } from 'react-i18next'
import { Languages } from 'lucide-react'
import { setLanguage, type Language } from '@/i18n'
import { useUiStore } from '@/stores/ui'
import { cn } from '@/lib/utils'

export function LanguageToggle() {
  const { i18n } = useTranslation()
  const setStoreLang = useUiStore((s) => s.setLanguage)
  const current = i18n.language === 'fa' ? 'fa' : 'en'

  function switchTo(lang: Language) {
    setLanguage(lang)
    setStoreLang(lang)
  }

  return (
    <div
      className="flex items-center rounded-md border border-gf-border text-sm"
      data-testid="language-toggle"
    >
      <Languages className="mx-1.5 size-4 text-gf-muted" />
      {(['en', 'fa'] as const).map((lang) => (
        <button
          key={lang}
          type="button"
          onClick={() => switchTo(lang)}
          className={cn(
            'px-2 py-1 font-medium transition-colors',
            current === lang ? 'text-gf-accent' : 'text-gf-muted hover:text-gf-text'
          )}
          aria-pressed={current === lang}
        >
          {lang === 'en' ? 'EN' : 'فا'}
        </button>
      ))}
    </div>
  )
}
