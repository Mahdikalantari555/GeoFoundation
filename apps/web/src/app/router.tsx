import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { PlaceholderPage } from '@/components/PlaceholderPage'
import { OverviewPage } from '@/features/workspace/OverviewPage'
import { SettingsPage } from '@/features/workspace/SettingsPage'
import { CollectionsPage } from '@/features/knowledge/CollectionsPage'
import { IngestPage } from '@/features/knowledge/IngestPage'
import { AssetsPage } from '@/features/knowledge/AssetsPage'
import { SearchPage } from '@/features/search/SearchPage'
import { AskPage } from '@/features/ask/AskPage'

export const routes = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'doctor', element: <PlaceholderPage milestone="M4" /> },
      { path: 'collections', element: <CollectionsPage /> },
      { path: 'ingest', element: <IngestPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'ask', element: <AskPage /> },
      { path: 'assets', element: <AssetsPage /> },
      { path: 'index', element: <PlaceholderPage milestone="M4" /> },
      { path: 'feedback', element: <PlaceholderPage milestone="M4" /> },
      { path: 'eval', element: <PlaceholderPage milestone="M4" /> },
      { path: 'agent', element: <PlaceholderPage milestone="M5" /> },
      { path: 'conversations', element: <PlaceholderPage milestone="M5" /> },
      { path: 'tools', element: <PlaceholderPage milestone="M5" /> },
      { path: 'playbooks', element: <PlaceholderPage milestone="M5" /> },
      { path: 'maps', element: <PlaceholderPage milestone="M6" /> },
      { path: 'farms', element: <PlaceholderPage milestone="M6" /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
