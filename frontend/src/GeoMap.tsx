import { useMemo } from 'react'
import { feature } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import world from 'world-atlas/countries-110m.json'
import type { Geo } from './api'

const W = 720, H = 360
const x = (lon: number) => ((lon + 180) / 360) * W
const y = (lat: number) => ((90 - lat) / 180) * H
type Pos = number[]
const ring = (r: Pos[]) => 'M' + r.map(([lo, la]) => `${x(lo).toFixed(1)},${y(la).toFixed(1)}`).join('L') + 'Z'

export default function GeoMap({ geo }: { geo: Geo | null }) {
  const d = useMemo(() => {
    const topo = world as unknown as Topology
    const fc = feature(topo, topo.objects.countries as GeometryCollection)
    return fc.features.map(f => {
      const g = f.geometry
      if (g.type === 'Polygon') return g.coordinates.map(ring).join('')
      if (g.type === 'MultiPolygon') return g.coordinates.map(p => p.map(ring).join('')).join('')
      return ''
    }).join('')
  }, [])
  const max = Math.max(1, ...(geo?.points.map(p => p.count) ?? [1]))
  return (<div>
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded bg-[#070b18]" role="img" aria-label="World map of attack sources">
      <path d={d} fill="#16213f" stroke="#243056" strokeWidth="0.4" />
      {geo?.points.map((p, i) => (<circle key={i} cx={x(p.lon)} cy={y(p.lat)} r={3 + 9 * Math.sqrt(p.count / max)} fill="#f87171" fillOpacity="0.55" stroke="#fecaca" strokeWidth="0.5"><title>{`${p.country}: ${p.count} events`}</title></circle>))}
    </svg>
    <p className="mt-2 text-xs text-slate-400">
      {!geo ? 'Loading…' : !geo.geoip_enabled ? 'GeoIP is off: set HIAB_GEOIP_DB to a MaxMind-format City database (not bundled; licence).'
        : `${geo.points.length} located location(s); ${geo.unlocated_ips} source IP(s) not locatable (private, proxy or unknown). Locations are approximate.`}</p>
  </div>)
}
