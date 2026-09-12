import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { GitBranch, Network, X } from 'lucide-react'
import { useEntityRelations, useEntities } from './hooks'
import { useWorkspace } from '@/features/workspace/hooks'
import type { Entity, EntityKind, EntityRelation } from '@/api/knowledge'
import { cn } from '@/lib/utils'

const KINDS: Array<{ value: EntityKind | 'all'; labelKey: string }> = [
  { value: 'all', labelKey: 'entities.allKinds' },
  { value: 'concept', labelKey: 'entities.kind.concept' },
  { value: 'location', labelKey: 'entities.kind.location' },
  { value: 'sensor', labelKey: 'entities.kind.sensor' },
  { value: 'product', labelKey: 'entities.kind.product' },
  { value: 'stress_type', labelKey: 'entities.kind.stress_type' },
  { value: 'metric', labelKey: 'entities.kind.metric' },
]

function entityName(value: Entity | string | null | undefined): string {
  if (typeof value === 'string') return value
  return value?.name ?? ''
}

function relationLabel(
  relation: EntityRelation,
  selected: Entity | null,
  selectedId: string,
): string {
  const source = entityName(relation.source ?? relation.source_entity ?? relation.source_id)
  const target = entityName(relation.target ?? relation.target_entity ?? relation.target_id)
  const selectedName = selected?.name ?? selectedId
  const predicate = relation.predicate || 'related to'
  if (source && target) return `${source} ${predicate} ${target}`
  if (source) return `${source} ${predicate} ${selectedName}`
  if (target) return `${selectedName} ${predicate} ${target}`
  return `${selectedName} ${predicate}`
}

export function EntitiesPage() {
  const { t } = useTranslation()
  const { data: ws } = useWorkspace()
  const [kind, setKind] = useState<EntityKind | 'all'>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selectedKind = kind === 'all' ? undefined : kind
  const { data: entities, isLoading, error } = useEntities(selectedKind)
  const {
    data: relations,
    isLoading: relationsLoading,
    error: relationsError,
  } = useEntityRelations(selectedId)
  const selected = entities?.find((entity) => entity.id === selectedId) ?? null

  if (ws?.status !== 'open') {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <h1 className="text-2xl font-semibold">{t('entities.title')}</h1>
        <div className="rounded-lg border border-gf-border bg-gf-panel p-8 text-center text-sm text-gf-muted">
          {t('entities.closed')}
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5" data-testid="entities-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t('entities.title')}</h1>
          <p className="mt-1 text-sm text-gf-muted">{t('entities.hint')}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-gf-muted">
          {t('entities.filter')}
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as EntityKind | 'all')
              setSelectedId(null)
            }}
            className="rounded-md border border-gf-border bg-gf-panel px-3 py-1.5 text-sm outline-none focus:border-gf-accent"
            data-testid="entity-kind-filter"
          >
            {KINDS.map((item) => (
              <option key={item.value} value={item.value}>
                {t(item.labelKey)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <p className="py-10 text-center text-sm text-gf-muted" aria-live="polite">
          {t('common.loading')}
        </p>
      ) : error ? (
        <p
          className="rounded-md border border-gf-err/30 bg-gf-err/10 px-3 py-3 text-sm text-gf-err"
          role="alert"
        >
          {error instanceof Error ? error.message : String(error)}
        </p>
      ) : !entities?.length ? (
        <div className="rounded-lg border border-dashed border-gf-border bg-gf-panel p-8 text-center">
          <Network className="mx-auto mb-2 size-7 text-gf-muted" />
          <p className="text-sm font-medium">{t('entities.empty')}</p>
          <p className="mt-1 text-xs text-gf-muted">{t('entities.emptyHint')}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gf-border bg-gf-panel">
          <table className="w-full text-sm" data-testid="entities-table">
            <thead>
              <tr className="border-b border-gf-border text-start text-xs text-gf-muted">
                <th className="px-4 py-2.5 text-start font-medium">{t('entities.name')}</th>
                <th className="px-4 py-2.5 text-start font-medium">{t('entities.kindCol')}</th>
                <th className="px-4 py-2.5 text-start font-medium">{t('entities.location')}</th>
              </tr>
            </thead>
            <tbody>
              {entities.map((entity) => (
                <tr
                  key={entity.id}
                  onClick={() => setSelectedId(entity.id)}
                  className={cn(
                    'cursor-pointer border-b border-gf-border/50 transition-colors last:border-0 hover:bg-gf-accent-soft/40',
                    selectedId === entity.id && 'bg-gf-accent-soft/60',
                  )}
                  data-testid="entity-row"
                >
                  <td className="px-4 py-2.5 font-medium">{entity.name}</td>
                  <td className="px-4 py-2.5">
                    <span className="rounded-full border border-gf-border px-2 py-0.5 text-xs">
                      {t(`entities.kind.${entity.kind}`)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-gf-muted">
                    {entity.spatial_bbox
                      ? entity.spatial_bbox.map((value) => Number(value.toFixed(4))).join(', ')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedId && (
        <section
          className="rounded-lg border border-gf-border bg-gf-panel p-4"
          data-testid="entity-relations"
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <GitBranch className="size-4 text-gf-accent" />
                <h2 className="text-lg font-semibold">{t('entities.relations')}</h2>
                <span className="rounded-full border border-gf-border px-2 py-0.5 text-xs">
                  {selected?.name ?? selectedId}
                </span>
              </div>
              <p className="mt-1 text-xs text-gf-muted">{t('entities.relationsHint')}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              aria-label={t('common.cancel')}
              className="rounded-md border border-gf-border p-1.5 text-gf-muted hover:text-gf-text"
            >
              <X className="size-4" />
            </button>
          </div>

          {relationsLoading ? (
            <p className="py-4 text-center text-sm text-gf-muted">{t('common.loading')}</p>
          ) : relationsError ? (
            <p
              className="rounded-md border border-gf-err/30 bg-gf-err/10 px-3 py-3 text-sm text-gf-err"
              role="alert"
            >
              {relationsError instanceof Error ? relationsError.message : String(relationsError)}
            </p>
          ) : !relations?.length ? (
            <p className="py-4 text-center text-sm text-gf-muted">{t('entities.noRelations')}</p>
          ) : (
            <ul className="space-y-2">
              {relations.map((relation) => (
                <li
                  key={relation.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-gf-border bg-gf-bg px-3 py-2 text-sm"
                >
                  <span className="min-w-0 break-all">
                    {relationLabel(relation, selected, selectedId)}
                  </span>
                  {typeof relation.confidence === 'number' && (
                    <span className="ms-auto rounded-full bg-gf-accent-soft px-2 py-0.5 text-xs text-gf-accent">
                      {Math.round(relation.confidence * 100)}%
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
