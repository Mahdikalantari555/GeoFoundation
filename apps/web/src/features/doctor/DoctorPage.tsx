import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useDoctor, useDoctorLlm } from './hooks'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gf-muted">{title}</h2>
      {children}
    </div>
  )
}

function StatusBadge({ ok, okLabel, failLabel }: { ok: boolean; okLabel: string; failLabel: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ok ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}
    >
      {ok ? okLabel : failLabel}
    </span>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gf-border/60 py-1.5 text-sm last:border-b-0">
      <span className="text-gf-muted">{label}</span>
      <span className="text-gf-text">{children}</span>
    </div>
  )
}

function CheckList({ checks }: { checks: Record<string, unknown> }) {
  const { t } = useTranslation()
  const entries = Object.entries(checks)
  if (entries.length === 0) return <p className="text-sm text-gf-muted">—</p>
  return (
    <div className="space-y-0.5">
      {entries.map(([key, value]) => {
        const label = key.replace(/_/g, ' ')
        if (typeof value === 'boolean') {
          return (
            <div key={key} className="flex items-center justify-between py-1 text-sm">
              <span className="capitalize text-gf-muted">{label}</span>
              <StatusBadge ok={value} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
            </div>
          )
        }
        if (typeof value === 'string' || typeof value === 'number') {
          return (
            <div key={key} className="py-1 text-sm">
              <span className="capitalize text-gf-muted">{label}: </span>
              <span className="font-mono text-xs text-gf-text">{String(value)}</span>
            </div>
          )
        }
        if (value === null) {
          return (
            <div key={key} className="py-1 text-sm">
              <span className="capitalize text-gf-muted">{label}: </span>
              <span className="font-mono text-xs text-gf-muted">null</span>
            </div>
          )
        }
        // Should never happen after server flatten, but guard against [object Object]
        return (
          <div key={key} className="py-1 text-sm">
            <span className="capitalize text-gf-muted">{label}: </span>
            <span className="font-mono text-xs text-gf-muted">—</span>
          </div>
        )
      })}
    </div>
  )
}

function DiagnosticsSection({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-md border border-gf-border/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium text-gf-text hover:bg-gf-bg"
      >
        <span>{title}</span>
        <span className="text-xs text-gf-muted">{open ? '−' : '+'}</span>
      </button>
      {open && <div className="border-t border-gf-border/60 px-3 py-2">{children}</div>}
    </div>
  )
}

export function DoctorPage() {
  const { t } = useTranslation()
  const { data: doctor, isLoading: doctorLoading, error: doctorError } = useDoctor()
  const { data: llm, isLoading: llmLoading } = useDoctorLlm()

  const env = (doctor?.environment ?? {}) as Record<string, unknown>
  const optionalDeps = (env.optional_deps as Record<string, unknown>) ?? {}
  const diagnostics = (doctor?.diagnostics ?? {}) as Record<string, Record<string, unknown>>
  const resolvedRoot = (doctor?.resolved_workspace_root as string) ?? null

  const llmKeySet = Boolean(llm?.key_set ?? llm?.key_configured)
  const llmBaseUrl = (llm?.base_url ?? (llm as unknown as Record<string, unknown>)?.api_base_url ?? null) as string | null
  const emb = (doctor?.embedding ?? {}) as Record<string, unknown>
  const diagEmbedding = (diagnostics.embedding ?? emb) as Record<string, unknown>
  const diagSqlite = (diagnostics.sqlite_vec ?? {}) as Record<string, unknown>
  const diagQdrant = (diagnostics.qdrant ?? {}) as Record<string, unknown>
  const diagPdf = (diagnostics.pdf_parser ?? {}) as Record<string, unknown>
  const diagVision = (diagnostics.vision ?? {}) as Record<string, unknown>
  const diagLlm = (diagnostics.llm ?? {}) as Record<string, unknown>

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.doctor')}</h1>

      {resolvedRoot && (
        <p className="text-xs text-gf-muted">
          {t('doctor.resolvedRoot')}: <span className="font-mono text-gf-text">{resolvedRoot}</span>
        </p>
      )}

      {doctorLoading && <p className="text-sm text-gf-muted">Loading diagnostics…</p>}
      {doctorError && (
        <p className="text-sm text-gf-err" role="alert">
          {doctorError.message}
        </p>
      )}

      {doctor && (
        <>
          <Section title={t('doctor.environment')}>
            <div className="space-y-2">
              <Row label={t('doctor.python')}>
                <span className="font-mono">{String(env.python_version ?? '—').slice(0, 30)}</span>
                <span className="ms-2">
                  <StatusBadge ok={Boolean(env.python_ok)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                </span>
              </Row>
              <Row label={t('doctor.core')}>
                <StatusBadge ok={Boolean(env.core_ok)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
              </Row>
              <div className="pt-1">
                <p className="mb-1 text-xs uppercase tracking-wide text-gf-muted">{t('doctor.optionalDeps')}</p>
                {Object.keys(optionalDeps).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(optionalDeps).map(([name, ok]) => (
                      <span
                        key={name}
                        className={`rounded-md px-2 py-0.5 text-xs ${ok ? 'bg-green-100 text-green-800' : 'bg-gf-border text-gf-muted'}`}
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </Section>

          <Section title={t('doctor.workspace')}>
            {doctor.workspace?.closed ? (
              <p className="text-sm text-gf-muted">{t('doctor.closed')}</p>
            ) : (
              <>
                <Row label={t('doctor.ok')}>
                  <StatusBadge ok={Boolean(doctor.workspace?.ok)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                </Row>
                <CheckList checks={(doctor.workspace?.checks ?? {}) as Record<string, unknown>} />
              </>
            )}
          </Section>

          <Section title={t('doctor.openProbe')}>
            {doctor.workspace_open?.closed ? (
              <p className="text-sm text-gf-muted">{t('doctor.closed')}</p>
            ) : (
              <>
                <Row label={t('doctor.ok')}>
                  <StatusBadge ok={Boolean(doctor.workspace_open?.ok)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                </Row>
                <CheckList checks={(doctor.workspace_open?.checks ?? {}) as Record<string, unknown>} />
              </>
            )}
          </Section>

          <Section title={t('doctor.diagnostics')}>
            <div className="space-y-3">
              <DiagnosticsSection title={t('doctor.llm')} defaultOpen>
                {Object.keys(diagLlm).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="space-y-1">
                    <Row label={t('doctor.provider')}>
                      <span className="font-mono">{String(diagLlm.provider ?? '—')}</span>
                    </Row>
                    <Row label={t('doctor.model')}>
                      <span className="font-mono text-xs">{String(diagLlm.model_id ?? '—')}</span>
                    </Row>
                    <Row label={t('doctor.baseUrl')}>
                      <span className="font-mono text-xs">{String(diagLlm.base_url ?? diagLlm.api_base_url ?? '—')}</span>
                    </Row>
                    <Row label={t('doctor.keyEnv')}>
                      <span className="font-mono text-xs">{String(diagLlm.key_env ?? '—')}</span>
                    </Row>
                    <Row label={t('doctor.keySet')}>
                      <StatusBadge ok={Boolean(diagLlm.key_configured ?? diagLlm.key_set)} okLabel={t('doctor.keySet')} failLabel={t('doctor.keyMissing')} />
                    </Row>
                    <Row label={t('doctor.contextWindow')}>
                      <span className="font-mono">{String(diagLlm.context_window ?? '—')}</span>
                    </Row>
                  </div>
                )}
              </DiagnosticsSection>

              <DiagnosticsSection title={t('doctor.qdrant')}>
                {Object.keys(diagQdrant).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="space-y-1">
                    <Row label={t('doctor.qdrantUrl')}>
                      <span className="font-mono text-xs">{String(diagQdrant.url ?? '—')}</span>
                    </Row>
                    <Row label={t('doctor.qdrantReachable')}>
                      <StatusBadge ok={Boolean(diagQdrant.reachable)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                    <Row label="client installed">
                      <StatusBadge ok={Boolean(diagQdrant.client_installed)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                  </div>
                )}
              </DiagnosticsSection>

              <DiagnosticsSection title={t('doctor.pdfParser')}>
                {Object.keys(diagPdf).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="space-y-1">
                    <Row label={t('doctor.pdfResolved')}>
                      <span className="font-mono">{String(diagPdf.resolved ?? '—')}</span>
                    </Row>
                    <Row label="opendataloader">
                      <StatusBadge ok={Boolean(diagPdf.opendataloader_installed)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                    <Row label="java available">
                      <StatusBadge ok={Boolean(diagPdf.java_available)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                  </div>
                )}
              </DiagnosticsSection>

              <DiagnosticsSection title={t('doctor.vision')}>
                {Object.keys(diagVision).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="space-y-1">
                    <Row label={t('doctor.visionCheckpoint')}>
                      <StatusBadge ok={Boolean(diagVision.checkpoint_exists)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                    <Row label="torch installed">
                      <StatusBadge ok={Boolean(diagVision.torch_installed)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                    <Row label="vision path">
                      <span className="font-mono text-xs">{String(diagVision.vision_path ?? '—')}</span>
                    </Row>
                  </div>
                )}
              </DiagnosticsSection>

              <DiagnosticsSection title={t('doctor.embedding')}>
                <div className="space-y-1">
                  <Row label={t('doctor.hubCount')}>
                    <span className="font-mono">{String(diagEmbedding.hub_count ?? emb.hub_count ?? 0)}</span>
                  </Row>
                  <Row label={t('doctor.downloaded')}>
                    <span className="font-mono">{String(diagEmbedding.downloaded ?? emb.downloaded ?? 0)}</span>
                  </Row>
                  <Row label={t('doctor.activeBackend')}>
                    <span className="font-mono">{String(diagEmbedding.active_backend ?? emb.active_backend ?? '—')}</span>
                  </Row>
                  <Row label={t('doctor.activeModel')}>
                    <span className="font-mono text-xs">{String(diagEmbedding.active_model ?? emb.active_model ?? '—')}</span>
                  </Row>
                  {Boolean(diagEmbedding.active_space_id) && (
                    <Row label={t('doctor.activeSpaceId')}>
                      <span className="font-mono text-xs">{String(diagEmbedding.active_space_id as string)}</span>
                    </Row>
                  )}
                </div>
              </DiagnosticsSection>

              <DiagnosticsSection title={t('doctor.sqliteVec')}>
                {Object.keys(diagSqlite).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="space-y-1">
                    <Row label={t('doctor.sqliteVecInstalled')}>
                      <StatusBadge ok={Boolean(diagSqlite.installed)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                    <Row label={t('doctor.sqliteVecLoadable')}>
                      <StatusBadge ok={Boolean(diagSqlite.loadable)} okLabel={t('doctor.ok')} failLabel={t('doctor.fail')} />
                    </Row>
                    <Row label={t('doctor.sqliteVecVersion')}>
                      <span className="font-mono text-xs">{String(diagSqlite.version ?? '—')}</span>
                    </Row>
                  </div>
                )}
              </DiagnosticsSection>
            </div>
          </Section>
        </>
      )}

      <Section title={t('doctor.llm')}>
        {llmLoading && <p className="text-sm text-gf-muted">Probing…</p>}
        {llm && (
          <div className="space-y-1">
            <Row label={t('doctor.provider')}>
              <span className="font-mono">{llm.provider ?? '—'}</span>
            </Row>
            <Row label={t('doctor.model')}>
              <span className="font-mono">{llm.model_id ?? '—'}</span>
            </Row>
            <Row label={t('doctor.baseUrl')}>
              <span className="font-mono text-xs">{llmBaseUrl ?? '—'}</span>
            </Row>
            <Row label={t('doctor.keyEnv')}>
              <span className="font-mono text-xs">{llm.key_env}</span>
            </Row>
            <Row label={t('doctor.contextWindow')}>
              <span className="font-mono">{llm.context_window ?? '—'}</span>
            </Row>
            <Row label={t('doctor.keySet')}>
              <StatusBadge ok={llmKeySet} okLabel={t('doctor.keySet')} failLabel={t('doctor.keyMissing')} />
            </Row>
          </div>
        )}
      </Section>
    </div>
  )
}
