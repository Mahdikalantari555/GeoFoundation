import { create } from 'zustand'

interface UiState {
  language: 'en' | 'fa'
  sidebarOpen: boolean
  setLanguage: (lang: 'en' | 'fa') => void
  toggleSidebar: () => void
}

export const useUiStore = create<UiState>((set) => ({
  language: 'en',
  sidebarOpen: true,
  setLanguage: (language) => set({ language }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))
