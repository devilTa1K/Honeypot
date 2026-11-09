import { useEffect, type ReactNode } from 'react'
import { animate, motion, useMotionValue, useTransform } from 'framer-motion'

export const Card = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="rounded-lg border border-[#243056] bg-[#0f1630] p-4"><h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</h2>{children}</section>)

export function Counter({ value }: { value: number }) {
  const mv = useMotionValue(0), text = useTransform(mv, v => Math.round(v).toLocaleString())
  useEffect(() => { const c = animate(mv, value, { duration: 0.6, ease: 'easeOut' }); return () => c.stop() }, [value, mv])
  return <motion.span>{text}</motion.span>
}
export const fmtTime = (t: number) => new Date(t * 1000).toLocaleString()
export const th = 'px-2 py-1 text-left text-[10px] uppercase tracking-wider text-slate-500'
export const td = 'px-2 py-1 font-mono text-xs'
export const input = 'rounded border border-[#243056] bg-[#070b18] px-2 py-1 text-xs'
