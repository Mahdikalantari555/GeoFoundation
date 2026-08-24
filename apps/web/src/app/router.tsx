import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from './AppShell'
import { PlaceholderPage } from '@/components/PlaceholderPage'

export const routes = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <PlaceholderPage milestone="M1" /> },
      { path: 'settings', element: <PlaceholderPage milestone="M1" /> },
      { path: 'doctor', element: <PlaceholderPage milestone="M4" /> },
      { path: 'collections', element: <PlaceholderPage milestone="M2" /> },
      { path: 'ingest', element: <PlaceholderPage milestone="M2" /> },
      { path: 'search', element: <PlaceholderPage milestone="M3" /> },
      { path: 'ask', element: <PlaceholderPage milestone="M3" /> },
      { path: 'assets', element: <PlaceholderPage milestone="M2" /> },
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
