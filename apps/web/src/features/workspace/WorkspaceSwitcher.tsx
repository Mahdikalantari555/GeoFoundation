import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FolderOpen, Plus, X } from 'lucide-react'
import { useCloseWorkspace, useCreateWorkspace, useOpenWorkspace } from './hooks'

export function WorkspaceSwitcher() {
  const { t } = useTranslation()
  const open = useOpenWorkspace()
  const create = useCreateWorkspace()
  const close = useCloseWorkspace()
  const [path, setPath] = useState('')
  const [name, setName] = useState('')

  function submitOpen() {
    if (!path.trim()) return
    open.mutate({ path: path.trim() })
  }

  function submitCreate() {
    if (!path.trim() || !name.trim()) return
    create.mutate({ path: path.trim(), name: name.trim(), offline: true })
  }

  return (
    <div className="flex items-center gap-2" data-testid="workspace-switcher">
      <FolderOpen className="size-4 text-gf-accent" />
      <input
        value={path}
        onChange={(e) => setPath(e.target.value)}
        placeholder={t('workspace.pathPlaceholder')}
        className="w-56 rounded-md border border-gf-border bg-gf-bg px-2 py-1 text-sm outline-none focus:border-gf-accent"
        aria-label={t('workspace.pathPlaceholder')}
      />
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t('workspace.namePlaceholder')}
        className="w-40 rounded-md border border-gf-border bg-gf-bg px-2 py-1 text-sm outline-none focus:border-gf-accent"
        aria-label={t('workspace.namePlaceholder')}
      />
      <button
        type="button"
        onClick={submitOpen}
        disabled={open.isPending || !path.trim()}
        className="flex items-center gap-1 rounded-md border border-gf-border px-2.5 py-1 text-sm disabled:opacity-50"
      >
        {t('common.open')}
      </button>
      <button
        type="button"
        onClick={submitCreate}
        disabled={create.isPending || !path.trim() || !name.trim()}
        className="flex items-center gap-1 rounded-md bg-gf-accent px-2.5 py-1 text-sm font-medium text-white disabled:opacity-50"
      >
        <Plus className="size-3.5" /> {t('common.create')}
      </button>
      <button
        type="button"
        onClick={() => close.mutate()}
        disabled={close.isPending}
        title={t('common.close')}
        className="rounded-md border border-gf-border p-1.5 text-gf-muted transition-colors hover:border-gf-err hover:text-gf-err disabled:opacity-50"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}
