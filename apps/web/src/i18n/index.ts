import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './en.json'
import fa from './fa.json'

export type Language = 'en' | 'fa'
export const LANGUAGES: Language[] = ['en', 'fa']
const STORAGE_KEY = 'gf.language'

function initialLanguage(): Language {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'en' || stored === 'fa') return stored
  return navigator.language.startsWith('fa') ? 'fa' : 'en'
}

export function applyDirection(lang: Language): void {
  document.documentElement.lang = lang
  document.documentElement.dir = lang === 'fa' ? 'rtl' : 'ltr'
}

export function setLanguage(lang: Language): void {
  localStorage.setItem(STORAGE_KEY, lang)
  void i18n.changeLanguage(lang)
  applyDirection(lang)
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    fa: { translation: fa },
  },
  lng: initialLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

applyDirection(i18n.language as Language)

export default i18n
