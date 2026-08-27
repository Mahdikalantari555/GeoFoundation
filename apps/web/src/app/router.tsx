import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { PlaceholderPage } from '@/components/PlaceholderPage'
import { OverviewPage } from '@/features/workspace/OverviewPage'
import { SettingsPage } from '@/features/workspace/SettingsPage'
import { DoctorPage } from '@/features/doctor/DoctorPage'
import { IndexPage } from '@/features/index/IndexPage'
import { ReviewPage } from '@/features/feedback/ReviewPage'
import { EvalPage } from '@/features/eval/EvalPage'
import { CollectionsPage } from '@/features/knowledge/CollectionsPage'
import { IngestPage } from '@/features/knowledge/IngestPage'
import { AssetsPage } from '@/features/knowledge/AssetsPage'
import { SearchPage } from '@/features/search/SearchPage'
import { AskPage } from '@/features/ask/AskPage'
import { AgentChatPage } from '@/features/agent/AgentChatPage'
import { ConversationsPage } from '@/features/agent/ConversationsPage'
import { ToolsPage } from '@/features/agent/ToolsPage'
import { PlaybooksPage } from '@/features/agent/PlaybooksPage'

export const routes = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'doctor', element: <DoctorPage /> },
      { path: 'collections', element: <CollectionsPage /> },
      { path: 'ingest', element: <IngestPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'ask', element: <AskPage /> },
      { path: 'assets', element: <AssetsPage /> },
      { path: 'index', element: <IndexPage /> },
      { path: 'feedback', element: <ReviewPage /> },
      { path: 'eval', element: <EvalPage /> },
      { path: 'agent', element: <AgentChatPage /> },
      { path: 'conversations', element: <ConversationsPage /> },
      { path: 'tools', element: <ToolsPage /> },
      { path: 'playbooks', element: <PlaybooksPage /> },
      { path: 'maps', element: <PlaceholderPage milestone="M6" /> },
      { path: 'farms', element: <PlaceholderPage milestone="M6" /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
