import { useTranslation } from 'react-i18next'
import { useDoctor, useDoctorLlm } from './hooks'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gf-border bg-gf-panel p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gf-muted">
        {title}
      </h2>
      {children}
    </div>
  )
}

function StatusBadge({ ok, okLabel, failLabel }: { ok: boolean; okLabel: string; failLabel: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}
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
  if (entries.length === 0) {
    return <p className="text-sm text-gf-muted">—</p>
  }
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
        return (
          <div key={key} className="py-1 text-sm">
            <span className="capitalize text-gf-muted">{label}: </span>
            <span className="font-mono text-xs text-gf-text">{String(value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export function DoctorPage() {
  const { t } = useTranslation()
  const { data: doctor, isLoading: doctorLoading, error: doctorError } = useDoctor()
  const { data: llm, isLoading: llmLoading } = useDoctorLlm()

  const env = (doctor?.environment ?? {}) as Record<string, unknown>
  const optionalDeps = (env.optional_deps as Record<string, unknown>) ?? {}

  const llmKeySet = Boolean(llm?.key_set ?? llm?.key_configured)
  const llmBaseUrl = llm?.base_url ?? llm?.api_base_url ?? null

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h1 className="text-2xl font-semibold">{t('nav.doctor')}</h1>

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
                <span className="font-mono">{String(env.python_version ?? '—').slice(0, 12)}</span>
                <span className="ms-2">
                  <StatusBadge
                    ok={Boolean(env.python_ok)}
                    okLabel={t('doctor.ok')}
                    failLabel={t('doctor.fail')}
                  />
                </span>
              </Row>
              <Row label={t('doctor.core')}>
                <StatusBadge
                  ok={Boolean(env.core_ok)}
                  okLabel={t('doctor.ok')}
                  failLabel={t('doctor.fail')}
                />
              </Row>
              <div className="pt-1">
                <p className="mb-1 text-xs uppercase tracking-wide text-gf-muted">
                  {t('doctor.optionalDeps')}
                </p>
                {Object.keys(optionalDeps).length === 0 ? (
                  <p className="text-sm text-gf-muted">—</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(optionalDeps).map(([name, ok]) => (
                      <span
                        key={name}
                        className={`rounded-md px-2 py-0.5 text-xs ${
                          ok
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gf-border text-gf-muted'
                        }`}
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
                  <StatusBadge
                    ok={Boolean(doctor.workspace?.ok)}
                    okLabel={t('doctor.ok')}
                    failLabel={t('doctor.fail')}
                  />
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
                  <StatusBadge
                    ok={Boolean(doctor.workspace_open?.ok)}
                    okLabel={t('doctor.ok')}
                    failLabel={t('doctor.fail')}
                  />
                </Row>
                <CheckList
                  checks={(doctor.workspace_open?.checks ?? {}) as Record<string, unknown>}
                />
              </>
            )}
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
              <StatusBadge
                ok={llmKeySet}
                okLabel={t('doctor.keySet')}
                failLabel={t('doctor.keyMissing')}
              />
            </Row>
          </div>
        )}
      </Section>
    </div>
  )
}
