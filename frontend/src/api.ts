export type Ev = { session: string; ip: string; method: string; path: string; ua: string; body: string; label: string; ts: number }
export type Step = { t: number; method: string; path: string; label: string; body: string }
export type Report = { session: string; events: number; ip: string; stages_observed: string[]; risk: string; summary: string }
export type Investigation = { session: string; summary: string; risk: string; confidence: number; stages: string[]; tactics: string[]; recommendations: string[]; source: 'llm' | 'deterministic' }
export const LABELS = ['reconnaissance', 'enumeration', 'credential_probing', 'data_discovery_attempt', 'exploitation_attempt', 'privilege_escalation_attempt']
export const TEXT: Record<string, string> = {
  reconnaissance: 'text-blue-400', enumeration: 'text-yellow-300', credential_probing: 'text-orange-400',
  data_discovery_attempt: 'text-pink-400', exploitation_attempt: 'text-red-400', privilege_escalation_attempt: 'text-red-500' }
export const BAR: Record<string, string> = {
  reconnaissance: 'bg-blue-500', enumeration: 'bg-yellow-400', credential_probing: 'bg-orange-500',
  data_discovery_attempt: 'bg-pink-500', exploitation_attempt: 'bg-red-500', privilege_escalation_attempt: 'bg-red-600' }
export const tokenGet = () => { try { return sessionStorage.getItem('hiab_token') || '' } catch { return '' } }
export const tokenSet = (t: string) => { try { sessionStorage.setItem('hiab_token', t) } catch { /* storage unavailable */ } }
export async function api<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, { ...init, headers: { 'x-admin-token': token, ...(init.headers || {}) } })
  if (!r.ok) throw new Error(r.status === 401 ? 'Unauthorized: check admin token' : `HTTP ${r.status}`)
  return r.json() as Promise<T>
}

export type GeoPoint = { lat: number; lon: number; country: string; count: number }
export type Geo = { geoip_enabled: boolean; unlocated_ips: number; points: GeoPoint[] }
export type MapPoint = GeoPoint & { sim?: boolean }   // sim = simulated sample, never real traffic
export type Env = { id: string; name: string; industry: string; size: number; port: number | null; status: string; event_count: number; active: boolean }
export type Intel = {
  totals: { events: number; sources: number; sessions: number }
  top_ips: { ip: string; count: number; sessions: number; labels: string[]; last: number }[]
  credentials: { username: string; password: string; accepted: boolean; count: number }[]
  commands: { command: string; count: number }[]; paths: { path: string; count: number }[]
  tactics: { tactic: string; count: number }[]; iocs: { kind: string; value: string; count: number }[]
  sessions: { session: string; ip: string; events: number; stages: string[]; risk: string; last: number }[] }
export type SettingsInfo = { settings: Record<string, number>; defaults: Record<string, number>
  runtime: { database: string; redis: boolean; geoip: boolean; investigations: Record<string, number>; version: string } }
export const jsonInit = (method: string, body: unknown): RequestInit => ({ method, headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
