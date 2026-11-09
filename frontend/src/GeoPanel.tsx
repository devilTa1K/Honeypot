import { lazy, Suspense, useCallback, useMemo, useState } from 'react'
import GeoMap from './GeoMap'
import type { Geo, MapPoint } from './api'

const Globe3D = lazy(() => import('./Globe3D'))
// Illustrative only: shown when the operator ticks "simulated sample". Never mixed into real statistics.
const SAMPLE: MapPoint[] = [
  { country: 'US', lat: 37.4, lon: -122.1, count: 42 }, { country: 'BR', lat: -23.5, lon: -46.6, count: 18 }, { country: 'DE', lat: 50.1, lon: 8.7, count: 30 },
  { country: 'NL', lat: 52.4, lon: 4.9, count: 25 }, { country: 'RU', lat: 55.7, lon: 37.6, count: 36 }, { country: 'CN', lat: 31.2, lon: 121.5, count: 48 },
  { country: 'IN', lat: 19.1, lon: 72.9, count: 14 }, { country: 'VN', lat: 10.8, lon: 106.7, count: 20 }, { country: 'NG', lat: 6.5, lon: 3.4, count: 9 },
  { country: 'AU', lat: -33.9, lon: 151.2, count: 7 }, { country: 'JP', lat: 35.7, lon: 139.7, count: 12 }, { country: 'ZA', lat: -26.2, lon: 28.0, count: 6 },
].map(p => ({ ...p, sim: true }))

export default function GeoPanel({ geo }: { geo: Geo | null }) {
  const [view, setView] = useState<'3d' | '2d'>('3d'), [sim, setSim] = useState(false)
  const onFail = useCallback(() => setView('2d'), [])
  const points = useMemo<MapPoint[]>(() => [...(geo?.points ?? []), ...(sim ? SAMPLE : [])], [geo, sim])
  const flat: Geo | null = sim ? { geoip_enabled: true, unlocated_ips: geo?.unlocated_ips ?? 0, points } : geo
  const btn = (on: boolean) => `rounded px-2 py-0.5 text-xs ${on ? 'bg-emerald-800 text-white' : 'bg-slate-800 text-slate-300'}`
  return (<div>
    <div className="mb-2 flex flex-wrap items-center gap-2">
      <button className={btn(view === '3d')} onClick={() => setView('3d')}>3D globe</button>
      <button className={btn(view === '2d')} onClick={() => setView('2d')}>2D map</button>
      <label className="ml-auto flex items-center gap-1 text-xs text-slate-300"><input type="checkbox" checked={sim} onChange={e => setSim(e.target.checked)} /> show simulated sample attacks (not real traffic)</label>
    </div>
    {view === '3d'
      ? <Suspense fallback={<p className="p-6 text-xs text-slate-400">Loading 3D globe…</p>}><Globe3D points={points} onFail={onFail} /></Suspense>
      : <GeoMap geo={flat} />}
    <p className="mt-2 text-xs text-slate-400">
      {sim ? 'Amber markers are SIMULATED samples for demonstration. ' : ''}
      {!geo ? 'Loading…' : !geo.geoip_enabled ? 'No GeoIP database: real sources cannot be located (set HIAB_GEOIP_DB; private and proxy IPs are never plotted). '
        : `${geo.points.length} real location(s); ${geo.unlocated_ips} source IP(s) not locatable. Locations are approximate. `}
      Arcs end at the honeypot (set VITE_HONEYPOT_LAT / VITE_HONEYPOT_LON).</p>
  </div>)
}
