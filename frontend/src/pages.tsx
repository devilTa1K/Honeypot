import { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api, BAR, Env, Intel, jsonInit, LABELS, SettingsInfo, TEXT } from './api'
import { Card, Counter, fmtTime, input, td, th } from './ui'

function usePoll<T>(path: string, token: string, ms: number, setErr: (s: string) => void) {
  const [data, setData] = useState<T | null>(null)
  const load = useCallback(() => api<T>(path, token).then(d => { setData(d); setErr('') }).catch(e => setErr(String(e.message))), [path, token, setErr])
  useEffect(() => { load(); const h = window.setInterval(load, ms); return () => window.clearInterval(h) }, [load, ms])
  return [data, load] as const
}

export function Environments({ token, setErr }: { token: string; setErr: (s: string) => void }) {
  const [envs, load] = usePoll<Env[]>('/admin/environments', token, 5000, setErr)
  const [name, setName] = useState('Beta Corp'), [industry, setIndustry] = useState('Healthcare'), [size, setSize] = useState(40)
  const act = (path: string, method = 'POST') => api(path, token, { method }).then(() => load()).catch(e => setErr(String(e.message)))
  const create = () => api(`/admin/environments?${new URLSearchParams({ name, industry, size: String(size) })}`, token, { method: 'POST' }).then(() => load()).catch(e => setErr(String(e.message)))
  return (<div className="space-y-4">
    <Card title="Environments (one fake company each)">
      <div className="overflow-x-auto"><table className="w-full"><thead><tr>{['Name', 'Industry', 'Staff', 'Events', 'State', 'Port', 'Actions'].map(h => <th key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody>{(envs ?? []).map(e => (<motion.tr key={e.id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="border-t border-[#1c2748]">
          <td className={td}>{e.name} {e.active && <span className="ml-1 rounded bg-emerald-900 px-1.5 text-[10px] text-emerald-300">SERVED BY GLOBAL DECOY</span>}</td>
          <td className={td}>{e.industry}</td><td className={td}>{e.size}</td><td className={td}><Counter value={e.event_count} /></td>
          <td className={`${td} ${e.status === 'running' ? 'text-emerald-300' : 'text-slate-500'}`}>{e.status}</td><td className={td}>{e.port ?? '-'}</td>
          <td className={`${td} space-x-1`}>
            {!e.active && <button className="rounded bg-emerald-900 px-2 py-0.5" onClick={() => act(`/admin/environments/${e.id}/activate`)}>Activate</button>}
            <button className="rounded bg-slate-700 px-2 py-0.5" onClick={() => act(`/admin/environments/${e.id}/status?value=${e.status === 'running' ? 'stopped' : 'running'}`)}>{e.status === 'running' ? 'Stop' : 'Start'}</button>
            <button className="rounded bg-red-900 px-2 py-0.5" onClick={() => { if (confirm(`Delete ${e.name}? Captured events are kept.`)) act(`/admin/environments/${e.id}`, 'DELETE') }}>Delete</button></td>
        </motion.tr>))}</tbody></table>
        {envs && !envs.length && <p className="p-3 text-xs text-slate-500">No environments yet. Create one below or in Generator.</p>}</div>
    </Card>
    <Card title="New environment"><div className="flex flex-wrap gap-2">
      <input className={input} value={name} onChange={e => setName(e.target.value)} /><input className={input} value={industry} onChange={e => setIndustry(e.target.value)} />
      <input className={`${input} w-20`} type="number" min={5} max={200} value={size} onChange={e => setSize(Number(e.target.value))} />
      <button onClick={create} className="rounded bg-emerald-800 px-3 py-1 text-xs">Create</button></div></Card>
    <Card title="Dedicated container per company (run on the host)">
      <p className="mb-2 text-xs text-slate-400">The control plane has no Docker access by design. To give an environment its own isolated decoy container and port (8100-8119), run on the host:</p>
      <code className="block rounded bg-black/60 p-2 text-xs text-emerald-300">python scripts/provision.py up {envs?.[0]?.id ?? '&lt;environment-id&gt;'}</code></Card>
  </div>)
}

export function ThreatIntel({ token, setErr }: { token: string; setErr: (s: string) => void }) {
  const [d] = usePoll<Intel>('/admin/intel', token, 10000, setErr)
  if (!d) return <p className="text-xs text-slate-500">Loading…</p>
  const tmax = Math.max(1, ...d.tactics.map(t => t.count))
  const risk = (r: string) => r === 'high' ? 'text-red-400' : r === 'medium' ? 'text-yellow-300' : 'text-slate-300'
  return (<div className="space-y-4">
    <div className="grid grid-cols-3 gap-3">{([['Events analysed', d.totals.events], ['Source IPs', d.totals.sources], ['Sessions', d.totals.sessions]] as const).map(([n, v]) => (
      <div key={n} className="rounded border border-[#243056] bg-[#0f1630] p-4"><div className="text-2xl font-bold"><Counter value={v} /></div><div className="text-xs text-slate-400">{n}</div></div>))}</div>
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Top source IPs"><table className="w-full"><thead><tr><th className={th}>IP</th><th className={th}>Events</th><th className={th}>Sessions</th><th className={th}>Behaviour</th></tr></thead>
        <tbody>{d.top_ips.map(i => <tr key={i.ip} className="border-t border-[#1c2748]"><td className={td}>{i.ip}</td><td className={td}>{i.count}</td><td className={td}>{i.sessions}</td>
          <td className={td}>{i.labels.map(l => <span key={l} className={`mr-1 ${TEXT[l]}`}>{l.replace('_attempt', '')}</span>)}</td></tr>)}</tbody></table></Card>
      <Card title="MITRE ATT&CK tactics observed (attempts)">{d.tactics.map(t => (<div key={t.tactic} className="mb-2 text-xs"><div className="flex justify-between"><span>{t.tactic}</span><span>{t.count}</span></div>
        <div className="h-1.5 rounded bg-[#1c2748]"><motion.div className="h-1.5 rounded bg-emerald-500" initial={{ width: 0 }} animate={{ width: `${(t.count / tmax) * 100}%` }} /></div></div>))}
        {!d.tactics.length && <p className="text-xs text-slate-500">No activity yet.</p>}</Card>
      <Card title="Credentials tried (SSH)"><table className="w-full"><thead><tr><th className={th}>User</th><th className={th}>Password</th><th className={th}>Tries</th><th className={th}>Got in</th></tr></thead>
        <tbody>{d.credentials.map((c, i) => <tr key={i} className="border-t border-[#1c2748]"><td className={td}>{c.username}</td><td className={td}>{c.password}</td><td className={td}>{c.count}</td><td className={td}>{c.accepted ? 'yes (decoy)' : 'no'}</td></tr>)}</tbody></table></Card>
      <Card title="Indicators of compromise (URLs / IPs in commands)"><table className="w-full"><tbody>{d.iocs.map((o, i) => <tr key={i} className="border-t border-[#1c2748]"><td className={td}>{o.kind}</td><td className={`${td} break-all`}>{o.value}</td><td className={td}>{o.count}</td></tr>)}</tbody></table>
        {!d.iocs.length && <p className="text-xs text-slate-500">None yet. These come from wget/curl commands in the fake shell.</p>}</Card>
      <Card title="Commands run"><table className="w-full"><tbody>{d.commands.map((c, i) => <tr key={i} className="border-t border-[#1c2748]"><td className={`${td} break-all`}>{c.command}</td><td className={td}>{c.count}</td></tr>)}</tbody></table></Card>
      <Card title="Paths requested (HTTP)"><table className="w-full"><tbody>{d.paths.map((c, i) => <tr key={i} className="border-t border-[#1c2748]"><td className={`${td} break-all`}>{c.path}</td><td className={td}>{c.count}</td></tr>)}</tbody></table></Card>
    </div>
    <Card title="Sessions by risk (rule-based; attempts only, no success is ever claimed)"><table className="w-full"><thead><tr><th className={th}>Session</th><th className={th}>IP</th><th className={th}>Events</th><th className={th}>Risk</th><th className={th}>Stages</th><th className={th}>Last seen</th></tr></thead>
      <tbody>{d.sessions.map(s => <tr key={s.session} className="border-t border-[#1c2748]"><td className={td}>{s.session}</td><td className={td}>{s.ip}</td><td className={td}>{s.events}</td><td className={`${td} ${risk(s.risk)}`}>{s.risk}</td>
        <td className={td}>{s.stages.map(l => <span key={l} className={`mr-1 ${TEXT[l]}`}>{l.replace('_attempt', '')}</span>)}</td><td className={td}>{fmtTime(s.last)}</td></tr>)}</tbody></table>
      <p className="mt-2 text-[10px] text-slate-500">Classes: {LABELS.map(l => <span key={l} className={`mr-2 ${TEXT[l]}`}><span className={`mr-1 inline-block h-2 w-2 rounded-full ${BAR[l]}`} />{l}</span>)}</p></Card>
  </div>)
}

export function Settings({ token, setErr }: { token: string; setErr: (s: string) => void }) {
  const [info, load] = usePoll<SettingsInfo>('/admin/settings', token, 15000, setErr)
  const [audit, loadAudit] = usePoll<{ ts: number; action: string }[]>('/admin/audit', token, 15000, setErr)
  const [form, setForm] = useState<Record<string, number> | null>(null), [msg, setMsg] = useState('')
  useEffect(() => { if (info && !form) setForm(info.settings) }, [info, form])
  if (!info || !form) return <p className="text-xs text-slate-500">Loading…</p>
  const save = () => api('/admin/settings', token, jsonInit('PUT', form)).then(() => { setMsg('Saved. The decoy picks changes up within a few seconds.'); load(); loadAudit() }).catch(e => setMsg(`Not saved: ${e.message} (check ranges)`))
  const clean = () => api<{ purged: number; trimmed: number }>('/admin/maintenance', token, { method: 'POST' }).then(r => { setMsg(`Cleanup done: ${r.purged} expired, ${r.trimmed} over quota removed.`); loadAudit() }).catch(e => setMsg(String(e.message)))
  const f = (k: string, label: string, hint: string) => (<label className="block text-xs"><span className="text-slate-300">{label}</span> <span className="text-slate-500">{hint}</span>
    <input className={`${input} mt-1 block w-40`} type="number" value={form[k]} onChange={e => setForm({ ...form, [k]: Number(e.target.value) })} /></label>)
  const rt = info.runtime
  return (<div className="grid gap-4 md:grid-cols-2">
    <Card title="Capture limits"><div className="space-y-3">
      {f('rate_per_min', 'Stored events per source IP per minute', '(1-10000; extra requests are still answered)')}
      {f('retention_days', 'Retention in days', '(0 = keep forever)')}
      {f('max_events', 'Event quota (newest kept)', '(1000-10,000,000)')}
      <div className="flex gap-2"><button onClick={save} className="rounded bg-emerald-800 px-3 py-1 text-xs">Save</button><button onClick={clean} className="rounded bg-slate-700 px-3 py-1 text-xs">Run cleanup now</button></div>
      {msg && <p className="text-xs text-emerald-300">{msg}</p>}</div></Card>
    <Card title="Runtime"><table className="w-full"><tbody>{([['Version', rt.version], ['Database', rt.database], ['Redis live relay', rt.redis ? 'connected' : 'in-process'], ['GeoIP database', rt.geoip ? 'loaded' : 'not configured'],
      ['Investigations', Object.entries(rt.investigations).map(([k, v]) => `${k}: ${v}`).join(', ') || 'none stored yet']] as const).map(([k, v]) => <tr key={k} className="border-t border-[#1c2748]"><td className={td}>{k}</td><td className={td}>{v}</td></tr>)}</tbody></table>
      <p className="mt-2 text-[10px] text-slate-500">Secrets (admin token, DB and Redis passwords, LLM key) are environment-only and are never shown or editable here.</p></Card>
    <div className="md:col-span-2"><Card title="Admin audit log (newest last)"><div className="max-h-64 overflow-auto font-mono text-xs">{(audit ?? []).slice(-60).map((a, i) => <div key={i} className="border-b border-[#1c2748] py-0.5"><span className="text-slate-500">{fmtTime(a.ts)}</span> {a.action}</div>)}</div></Card></div>
  </div>)
}
