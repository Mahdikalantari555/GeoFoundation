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

function JsonBlock({ data }: { data: unknown }) {
  return (
    <pre className="overflow-x-auto whitespace-pre-wrap text-xs leading-relaxed text-gf-text">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}
    >
      {ok ? 'OK' : 'FAIL'}
    </span>
  )
}

export function DoctorPage() {
  const { t } = useTranslation()
  const { data: doctor, isLoading: doctorLoading, error: doctorError } = useDoctor()
  const { data: llm, isLoading: llmLoading } = useDoctorLlm()

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
          <Section title="Environment">
            <div className="flex items-center gap-3 text-sm">
              <span>Python {String((doctor.environment as Record<string, unknown>).python_version).slice(0, 6)}</span>
              <StatusBadge ok={Boolean((doctor.environment as Record<string, unknown>).python_ok)} />
              <StatusBadge ok={Boolean((doctor.environment as Record<string, unknown>).core_ok)} />
            </div>
            <JsonBlock data={(doctor.environment as Record<string, unknown>).optional_deps} />
          </Section>

          <Section title="Workspace">
            <StatusBadge ok={Boolean((doctor.workspace as Record<string, unknown>).ok)} />
            <JsonBlock data={(doctor.workspace as Record<string, unknown>).checks} />
          </Section>

          <Section title="Workspace Open Probe">
            <StatusBadge ok={Boolean((doctor.workspace_open as Record<string, unknown>).ok)} />
            <JsonBlock data={(doctor.workspace_open as Record<string, unknown>).checks} />
          </Section>
        </>
      )}

      <Section title="LLM Provider">
        {llmLoading && <p className="text-sm text-gf-muted">Probing…</p>}
        {llm && <JsonBlock data={llm} />}
      </Section>
    </div>
  )
}
