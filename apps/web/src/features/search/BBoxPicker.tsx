import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X } from 'lucide-react'

export type BBox = [number, number, number, number] // min_lon, min_lat, max_lon, max_lat

const W = 360
const H = 180

function lonToX(lon: number) {
  return lon + 180
}
function latToY(lat: number) {
  return 90 - lat
}

interface BBoxPickerProps {
  value: BBox | null
  onChange: (bbox: BBox | null) => void
}

/** Dependency-free world-graticule rectangle picker (EPSG:4326). */
export function BBoxPicker({ value, onChange }: BBoxPickerProps) {
  const { t } = useTranslation()
  const svgRef = useRef<SVGSVGElement>(null)
  const [draft, setDraft] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(
    null
  )
  const drawingRef = useRef(false)

  function pointFromEvent(e: React.PointerEvent<SVGSVGElement>): { lon: number; lat: number } {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const py = ((e.clientY - rect.top) / rect.height) * H
    return { lon: Math.min(180, Math.max(-180, px - 180)), lat: Math.min(90, Math.max(-90, 90 - py)) }
  }

  function onPointerDown(e: React.PointerEvent<SVGSVGElement>) {
    e.currentTarget.setPointerCapture(e.pointerId)
    const p = pointFromEvent(e)
    drawingRef.current = true
    setDraft({ x0: lonToX(p.lon), y0: latToY(p.lat), x1: lonToX(p.lon), y1: latToY(p.lat) })
  }

  function onPointerMove(e: React.PointerEvent<SVGSVGElement>) {
    if (!drawingRef.current) return
    const p = pointFromEvent(e)
    setDraft((d) => (d ? { ...d, x1: lonToX(p.lon), y1: latToY(p.lat) } : d))
  }

  function onPointerUp() {
    if (!drawingRef.current || !draft) return
    drawingRef.current = false
    const minLon = Math.min(draft.x0, draft.x1) - 180
    const maxLon = Math.max(draft.x0, draft.x1) - 180
    const minLat = 90 - Math.max(draft.y0, draft.y1)
    const maxLat = 90 - Math.min(draft.y0, draft.y1)
    setDraft(null)
    // Treat a click (no real drag) as a clear gesture.
    if (Math.abs(maxLon - minLon) < 1.5 || Math.abs(maxLat - minLat) < 1.5) {
      onChange(null)
      return
    }
    onChange([round(minLon), round(minLat), round(maxLon), round(maxLat)])
  }

  const rect = value
    ? { x: lonToX(value[0]), y: latToY(value[3]), w: value[2] - value[0], h: value[3] - value[1] }
    : null

  function updateCorner(idx: 0 | 1 | 2 | 3, raw: string) {
    const num = Number(raw)
    if (!value || Number.isNaN(num)) return
    const next: BBox = [...value] as BBox
    next[idx] = round(num)
    if (next[0] > next[2]) [next[0], next[2]] = [next[2], next[0]]
    if (next[1] > next[3]) [next[1], next[3]] = [next[3], next[1]]
    onChange(next)
  }

  return (
    <div className="space-y-2">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="h-36 w-full touch-none select-none rounded-md border border-gf-border bg-gf-bg"
        data-testid="bbox-picker"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        role="application"
        aria-label={t('search.filters.bboxPicker')}
      >
        {/* graticule */}
        {[...Array(11)].map((_, i) => (
          <line key={`v${i}`} x1={i * 30} y1={0} x2={i * 30} y2={H} stroke="currentColor" strokeWidth={i === 6 ? 0.8 : 0.3} className="text-gf-border" />
        ))}
        {[...Array(7)].map((_, i) => (
          <line key={`h${i}`} x1={0} y1={i * 30} x2={W} y2={i * 30} stroke="currentColor" strokeWidth={i === 3 ? 0.8 : 0.3} className="text-gf-border" />
        ))}
        {rect && (
          <rect
            x={rect.x}
            y={rect.y}
            width={Math.max(rect.w, 1)}
            height={Math.max(rect.h, 1)}
            fill="var(--gf-accent)"
            fillOpacity={0.25}
            stroke="var(--gf-accent)"
            strokeWidth={1.5}
          />
        )}
        {draft && (
          <rect
            x={Math.min(draft.x0, draft.x1)}
            y={Math.min(draft.y0, draft.y1)}
            width={Math.abs(draft.x1 - draft.x0)}
            height={Math.abs(draft.y1 - draft.y0)}
            fill="var(--gf-accent)"
            fillOpacity={0.15}
            stroke="var(--gf-accent)"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
        )}
      </svg>

      <div className="flex flex-wrap items-center gap-2">
        {(['minLon', 'minLat', 'maxLon', 'maxLat'] as const).map((label, idx) => (
          <input
            key={label}
            type="number"
            inputMode="decimal"
            step="any"
            aria-label={t(`search.filters.${label}`)}
            placeholder={t(`search.filters.${label}`)}
            disabled={!value}
            value={value?.[idx] ?? ''}
            onChange={(e) => updateCorner(idx as 0 | 1 | 2 | 3, e.target.value)}
            className="w-20 rounded border border-gf-border bg-gf-bg px-1.5 py-1 text-xs"
            data-testid={`bbox-${label}`}
          />
        ))}
        {value && (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="flex items-center gap-1 rounded border border-gf-border px-2 py-1 text-xs text-gf-muted hover:text-gf-err"
          >
            <X className="size-3" /> {t('search.filters.clear')}
          </button>
        )}
      </div>
    </div>
  )
}

function round(n: number) {
  return Math.round(n * 1000) / 1000
}
