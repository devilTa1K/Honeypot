import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import GeoPanel from './GeoPanel'
import { Environments, Settings, ThreatIntel } from './pages'
import { Card, Counter } from './ui'
import { api, BAR, Ev, Geo, Investigation, LABELS, Step, TEXT, tokenGet, tokenSet } from './api'

type Tab = 'overview' | 'live' | 'replay' | 'explorer' | 'intel' | 'envs' | 'generator' | 'settings'
const TABS: [Tab, string][] = [['overview', 'Overview'], ['live', 'Live Monitor'], ['replay', 'Session Replay'], ['explorer', 'Event Explorer'], ['intel', 'Threat Intel'], ['envs', 'Environments'], ['generator', 'Generator'], ['settings', 'Settings']]
const fmt = (t: number) => new Date(t * 1000).toLocaleTimeString()
const Row = ({ e }: { e: Ev }) => (
  <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }} className="flex gap-3 border-b border-[#1c2748] py-1 font-mono text-xs"><span className="text-slate-500">{fmt(e.ts)}</span><span className="w-28 shrink-0">{e.ip}</span>
    <span className="w-20 shrink-0">{e.method}</span><span className="flex-1 truncate">{e.path}</span><span className={TEXT[e.label]}>{e.label}</span></motion.div>)

export default function App() {
  const [tab, setTab] = useState<Tab>('overview')
  const [token, setToken] = useState(tokenGet())
  const [events, setEvents] = useState<Ev[]>([])
  const [live, setLive] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => {
    let ws: WebSocket | null = null, stop = false, retry = 0, ping = 0
    api<Ev[]>('/admin/events?limit=1000', token).then(d => { setEvents(d); setErr('') }).catch(e => setErr(String(e.message)))
    const connect = () => {
      ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws?token=${encodeURIComponent(token)}`)
      ws.onopen = () => { setLive(true); ping = window.setInterval(() => ws?.send('ping'), 20000) }
      ws.onmessage = m => setEvents(p => [JSON.parse(m.data) as Ev, ...p].slice(0, 2000))
      ws.onclose = () => { setLive(false); window.clearInterval(ping); if (!stop) retry = window.setTimeout(connect, 2000) }
    }
    connect()
    return () => { stop = true; window.clearTimeout(retry); window.clearInterval(ping); ws?.close() }
  }, [token])

  const kill = () => { if (confirm('EMERGENCY SHUTDOWN: all decoy services will return 503. Continue?')) api('/admin/kill', token, { method: 'POST' }).catch(e => setErr(String(e.message))) }
  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#243056] bg-[#0f1630] px-5 py-3">
        <div className="flex items-center gap-3"><h1 className="font-mono text-sm font-bold text-emerald-400">HONEYPOT-IN-A-BOX // SOC</h1>
          <span className={`rounded px-2 py-0.5 text-[10px] ${live ? 'bg-emerald-900 text-emerald-300' : 'bg-slate-800 text-slate-400'}`}>{live ? 'LIVE' : 'OFFLINE'}</span></div>
        <div className="flex items-center gap-2">
          <input type="password" placeholder="admin token" value={token} onChange={e => { setToken(e.target.value); tokenSet(e.target.value) }}
            className="w-36 rounded border border-[#243056] bg-[#070b18] px-2 py-1 text-xs" />
          <button onClick={kill} className="rounded bg-red-900 px-3 py-1 text-xs font-semibold text-white hover:bg-red-700">EMERGENCY SHUTDOWN</button></div>
      </header>
      <nav className="flex gap-1 px-5 pt-3">{TABS.map(([k, n]) => (
        <button key={k} onClick={() => setTab(k)} className={`rounded-t px-3 py-1.5 text-xs ${tab === k ? 'bg-[#0f1630] text-emerald-300' : 'text-slate-400 hover:text-white'}`}>{n}</button>))}</nav>
      {err && <p className="mx-5 mt-3 rounded bg-red-950 px-3 py-2 text-xs text-red-300">{err}</p>}
      <main className="p-5"><AnimatePresence mode="wait"><motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}>
        {tab === 'overview' && <Overview events={events} token={token} />}
        {tab === 'live' && <Card title={`Live attack feed (${events.length})`}><div className="max-h-[70vh] overflow-auto">{events.slice(0, 300).map(e => <Row key={`${e.ts}-${e.session}-${e.method}-${e.path}`} e={e} />)}{!events.length && <p className="text-xs text-slate-500">No events yet. Run scripts/attacker.py.</p>}</div></Card>}
        {tab === 'replay' && <Replay events={events} token={token} />}
        {tab === 'explorer' && <Explorer events={events} />}
        {tab === 'intel' && <ThreatIntel token={token} setErr={setErr} />}
        {tab === 'envs' && <Environments token={token} setErr={setErr} />}
        {tab === 'settings' && <Settings token={token} setErr={setErr} />}
        {tab === 'generator' && <Generator token={token} setErr={setErr} />}
      </motion.div></AnimatePresence></main>
    </div>)
}

function Overview({ events, token }: { events: Ev[]; token: string }) {
  const [geo, setGeo] = useState<Geo | null>(null)
  useEffect(() => {
    let on = true
    const load = () => api<Geo>('/admin/geo', token).then(g => { if (on) setGeo(g) }).catch(() => undefined)
    load(); const h = window.setInterval(load, 10000)
    return () => { on = false; window.clearInterval(h) }
  }, [token])
  const s = useMemo(() => {
    const counts: Record<string, number> = {}; events.forEach(e => { counts[e.label] = (counts[e.label] || 0) + 1 })
    const high = new Set(events.filter(e => e.label === 'exploitation_attempt' || e.label === 'privilege_escalation_attempt').map(e => e.session))
    const now = Date.now() / 1000, b: number[] = Array(30).fill(0)
    events.forEach(e => { const m = Math.floor((now - e.ts) / 60); if (m >= 0 && m < 30) b[29 - m]++ })
    return { counts, high: high.size, sessions: new Set(events.map(e => e.session)).size, ips: new Set(events.map(e => e.ip)).size, b }
  }, [events])
  const max = Math.max(1, ...Object.values(s.counts)), bmax = Math.max(1, ...s.b)
  const stat = (n: string, v: number) => <div className="rounded border border-[#243056] bg-[#0f1630] p-4"><div className="text-2xl font-bold"><Counter value={v} /></div><div className="text-xs text-slate-400">{n}</div></div>
  return (<div className="space-y-4">
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{stat('Events', events.length)}{stat('Sessions', s.sessions)}{stat('Unique source IPs', s.ips)}{stat('Sessions with exploit attempts', s.high)}</div>
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Classifications (attempts observed)">{LABELS.map(l => (<div key={l} className="mb-2 text-xs"><div className="flex justify-between"><span className={TEXT[l]}>{l}</span><span>{s.counts[l] || 0}</span></div>
        <div className="h-1.5 rounded bg-[#1c2748]"><div className={`h-1.5 rounded ${BAR[l]}`} style={{ width: `${((s.counts[l] || 0) / max) * 100}%` }} /></div></div>))}</Card>
      <Card title="Attack timeline (events per minute, last 30 min)"><div className="flex h-32 items-end gap-0.5">{s.b.map((v, i) => <div key={i} title={`${v}`} className="flex-1 rounded-t bg-emerald-500/70" style={{ height: `${(v / bmax) * 100}%`, minHeight: v ? 2 : 0 }} />)}</div></Card>
    </div>
    <Card title="Geographic view (public source IPs only)"><GeoPanel geo={geo} /></Card>
  </div>)
}

function Explorer({ events }: { events: Ev[] }) {
  const [label, setLabel] = useState(''), [q, setQ] = useState('')
  const rows = events.filter(e => (!label || e.label === label) && (!q || `${e.ip} ${e.path} ${e.body} ${e.ua}`.toLowerCase().includes(q.toLowerCase())))
  return (<Card title={`Event explorer (${rows.length}/${events.length})`}>
    <div className="mb-3 flex gap-2"><select value={label} onChange={e => setLabel(e.target.value)} className="rounded border border-[#243056] bg-[#070b18] px-2 py-1 text-xs"><option value="">all classes</option>{LABELS.map(l => <option key={l}>{l}</option>)}</select>
      <input value={q} onChange={e => setQ(e.target.value)} placeholder="search ip / path / body / user agent" className="flex-1 rounded border border-[#243056] bg-[#070b18] px-2 py-1 text-xs" /></div>
    <div className="max-h-[65vh] overflow-auto">{rows.slice(0, 500).map((e, i) => <Row key={i} e={e} />)}</div></Card>)
}

function Replay({ events, token }: { events: Ev[]; token: string }) {
  const sessions = useMemo(() => {
    const m = new Map<string, Ev[]>(); events.forEach(e => m.set(e.session, [...(m.get(e.session) || []), e]))
    return [...m.entries()].map(([id, l]) => ({ id, ip: l[0].ip, n: l.length, last: Math.max(...l.map(e => e.ts)) })).sort((a, b) => b.last - a.last)
  }, [events])
  const [sel, setSel] = useState(''), [steps, setSteps] = useState<Step[]>([]), [inv, setInv] = useState<Investigation | null>(null)
  const [idx, setIdx] = useState(0), [playing, setPlaying] = useState(false)
  useEffect(() => {
    if (!sel) return
    setPlaying(false); setIdx(0)
    api<Step[]>(`/admin/replay/${sel}`, token).then(setSteps).catch(() => setSteps([]))
    api<Investigation>(`/admin/analyze/${sel}`, token).then(setInv).catch(() => setInv(null))
  }, [sel, token])
  useEffect(() => {
    if (!playing) return
    if (idx >= steps.length) { setPlaying(false); return }
    const delay = idx === 0 ? 200 : Math.min(1500, (steps[idx].t - steps[idx - 1].t) * 1000)
    const h = window.setTimeout(() => setIdx(i => i + 1), delay)
    return () => window.clearTimeout(h)
  }, [playing, idx, steps])
  return (<div className="grid gap-4 md:grid-cols-[1fr_2fr]">
    <Card title="Sessions"><div className="max-h-[65vh] overflow-auto">{sessions.map(s => (
      <button key={s.id} onClick={() => setSel(s.id)} className={`block w-full border-b border-[#1c2748] px-1 py-1.5 text-left font-mono text-xs ${sel === s.id ? 'text-emerald-300' : ''}`}>{s.id} · {s.ip} · {s.n} req</button>))}
      {!sessions.length && <p className="text-xs text-slate-500">No sessions yet.</p>}</div></Card>
    <Card title="Attacker session replay">{!sel ? <p className="text-xs text-slate-500">Select a session.</p> : (<>
      <div className="mb-3 flex items-center gap-2"><button onClick={() => { if (idx >= steps.length) setIdx(0); setPlaying(p => !p) }} className="rounded bg-emerald-800 px-3 py-1 text-xs">{playing ? 'Pause' : 'Play'}</button>
        <button onClick={() => { setPlaying(false); setIdx(0) }} className="rounded bg-slate-800 px-3 py-1 text-xs">Reset</button><span className="text-xs text-slate-400">{Math.min(idx, steps.length)}/{steps.length}</span></div>
      <div className="min-h-40 rounded bg-black/60 p-3 font-mono text-xs">{steps.slice(0, idx).map((st, i) => (<div key={i}><span className="text-slate-500">+{st.t.toFixed(2)}s</span> {st.method} {st.path} <span className={TEXT[st.label]}>[{st.label}]</span>{st.body && <div className="pl-10 text-slate-400">{st.body}</div>}</div>))}</div>
      {inv && <div className="mt-3 space-y-2 rounded border border-[#243056] p-3 text-xs"><div className="font-semibold">Investigation · risk: <span className={inv.risk === 'high' ? 'text-red-400' : 'text-yellow-300'}>{inv.risk}</span> · confidence {Math.round(inv.confidence * 100)}% · <span className="rounded bg-slate-800 px-1.5 py-0.5">{inv.source}</span></div><p className="text-slate-300">{inv.summary}</p><div className="text-slate-400">ATT&amp;CK tactics: {inv.tactics.join(', ')}</div><ul className="list-disc pl-4 text-slate-300">{inv.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul></div>}</>)}</Card></div>)
}

function Generator({ token, setErr }: { token: string; setErr: (s: string) => void }) {
  const [name, setName] = useState('Acme Pay'), [industry, setIndustry] = useState('Fintech'), [size, setSize] = useState(50), [out, setOut] = useState('')
  const go = () => api<{ domain: string; employees: number }>(`/admin/company?${new URLSearchParams({ name, industry, size: String(size) })}`, token, { method: 'POST' })
    .then(r => { setOut(`Decoy environment live: ${r.domain} (${r.employees} synthetic employees)`); setErr('') }).catch(e => setErr(String(e.message)))
  const inp = 'rounded border border-[#243056] bg-[#070b18] px-2 py-1 text-xs'
  return (<Card title="Company generator"><div className="flex flex-wrap gap-2">
    <input className={inp} value={name} onChange={e => setName(e.target.value)} /><input className={inp} value={industry} onChange={e => setIndustry(e.target.value)} />
    <input className={`${inp} w-20`} type="number" min={5} max={200} value={size} onChange={e => setSize(Number(e.target.value))} />
    <button onClick={go} className="rounded bg-emerald-800 px-3 py-1 text-xs">Generate &amp; deploy</button></div>{out && <p className="mt-3 text-xs text-emerald-300">{out}</p>}</Card>)
}
