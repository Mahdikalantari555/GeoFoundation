import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught', error, info)
  }

  render() {
    if (this.state.error) {
      const err = this.state.error as Error & { code?: string }
      return (
        <div className="m-4 rounded-lg border border-gf-err/50 bg-gf-err/10 p-4" role="alert">
          <p className="text-sm font-medium text-gf-err">{err.message || 'Unexpected error'}</p>
          {err.code && <p className="text-xs text-gf-muted">code: {err.code}</p>}
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-2 rounded-md border border-gf-border px-3 py-1 text-xs"
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
