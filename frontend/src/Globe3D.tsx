import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { mesh } from 'topojson-client'
import type { GeometryCollection, Topology } from 'topojson-specification'
import world from 'world-atlas/countries-110m.json'
import type { MapPoint } from './api'
import dayUrl from './assets/earth-day.jpg'
import nightUrl from './assets/earth-night.jpg'
import bumpUrl from './assets/earth-bump.jpg'

// Where the honeypot "lives" (arcs end here). Override with VITE_HONEYPOT_LAT / VITE_HONEYPOT_LON.
const HP = { lat: Number(import.meta.env.VITE_HONEYPOT_LAT ?? 20), lon: Number(import.meta.env.VITE_HONEYPOT_LON ?? 0) }
const HEIGHT = 460

// Matches the UV layout of THREE.SphereGeometry with an equirectangular texture.
const toVec = (lat: number, lon: number, r = 1) => {
  const phi = ((90 - lat) * Math.PI) / 180, theta = ((lon + 180) * Math.PI) / 180
  return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta))
}

type Comet = { m: THREE.Mesh; c: THREE.QuadraticBezierCurve3; t: number }

export default function Globe3D({ points, onFail }: { points: MapPoint[]; onFail: () => void }) {
  const host = useRef<HTMLDivElement>(null)
  const setPointsRef = useRef<(p: MapPoint[]) => void>(() => undefined)
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)

  useEffect(() => {
    const el = host.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }) } catch { onFail(); return }
    const width = () => el.clientWidth || 640
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); renderer.setSize(width(), HEIGHT)
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(40, width() / HEIGHT, 0.1, 100); camera.position.set(0, 0.5, 3.1)
    const sun = new THREE.DirectionalLight(0xbcd4ff, 1.7); sun.position.set(3, 2, 4)
    camera.add(sun); camera.add(new THREE.AmbientLight(0x4466aa, 0.8)); scene.add(camera)   // lights follow the camera

    const loader = new THREE.TextureLoader(), aniso = renderer.capabilities.getMaxAnisotropy()
    const tex = (url: string, srgb: boolean) => { const t = loader.load(url); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = aniso; return t }
    const material = new THREE.MeshStandardMaterial({ map: tex(dayUrl, true), emissiveMap: tex(nightUrl, true), emissive: 0xffffff, emissiveIntensity: 0.85,
      bumpMap: tex(bumpUrl, false), bumpScale: 1.0, roughness: 0.95, metalness: 0, color: 0x7f93bb })
    const globe = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 96), material); scene.add(globe)

    // atmosphere glow
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.14, 64, 64), new THREE.ShaderMaterial({
      vertexShader: 'varying vec3 vN; void main(){ vN = normalize(normalMatrix * normal); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: 'varying vec3 vN; void main(){ float i = pow(max(0.0, 0.72 - dot(vN, vec3(0.0, 0.0, 1.0))), 3.0); gl_FragColor = vec4(0.25, 0.55, 1.0, 1.0) * i; }',
      blending: THREE.AdditiveBlending, side: THREE.BackSide, transparent: true, depthWrite: false })))

    // stars
    const sv: number[] = []
    for (let i = 0; i < 900; i++) { const v = new THREE.Vector3().randomDirection().multiplyScalar(30 + Math.random() * 20); sv.push(v.x, v.y, v.z) }
    scene.add(new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(sv, 3)), new THREE.PointsMaterial({ color: 0x9db4ff, size: 0.12, sizeAttenuation: true })))

    // country borders
    const topo = world as unknown as Topology
    const border = mesh(topo, topo.objects.countries as GeometryCollection, (a, b) => a !== b)
    const bv: number[] = []
    for (const line of border.coordinates) for (let i = 1; i < line.length; i++) {
      const a = toVec(line[i - 1][1], line[i - 1][0], 1.002), b = toVec(line[i][1], line[i][0], 1.002); bv.push(a.x, a.y, a.z, b.x, b.y, b.z)
    }
    scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(bv, 3)),
      new THREE.LineBasicMaterial({ color: 0x7fd4ff, transparent: true, opacity: 0.28 })))

    // markers, arcs and moving "packets"
    const markers = new THREE.Group(); scene.add(markers)
    const heads: THREE.Mesh[] = [], comets: Comet[] = []
    const disposeMarkers = () => {
      markers.traverse(o => { const m = o as THREE.Mesh; m.geometry?.dispose(); (m.material as THREE.Material | undefined)?.dispose() })
      markers.clear(); heads.length = 0; comets.length = 0
    }
    setPointsRef.current = (pts: MapPoint[]) => {
      disposeMarkers()
      const hpPos = toVec(HP.lat, HP.lon, 1.0)
      const hp = new THREE.Mesh(new THREE.SphereGeometry(0.02, 16, 16), new THREE.MeshBasicMaterial({ color: 0x35f0b0 })); hp.position.copy(hpPos.clone().multiplyScalar(1.01)); markers.add(hp)
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.036, 48), new THREE.MeshBasicMaterial({ color: 0x35f0b0, side: THREE.DoubleSide, transparent: true, opacity: 0.8 }))
      ring.position.copy(hpPos.clone().multiplyScalar(1.012)); ring.lookAt(hpPos.clone().multiplyScalar(2)); markers.add(ring)
      const max = Math.max(1, ...pts.map(p => p.count))
      for (const p of pts) {
        const k = Math.sqrt(p.count / max), h = 0.04 + 0.14 * k, color = p.sim ? 0xffb020 : 0xff5a5a
        const base = toVec(p.lat, p.lon, 1), up = base.clone().normalize()
        const pin = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, h, 8), new THREE.MeshBasicMaterial({ color }))
        pin.position.copy(base.clone().multiplyScalar(1 + h / 2)); pin.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), up); markers.add(pin)
        const head = new THREE.Mesh(new THREE.SphereGeometry(0.014 + 0.012 * k, 16, 16), new THREE.MeshBasicMaterial({ color }))
        head.position.copy(base.clone().multiplyScalar(1 + h)); head.userData.label = `${p.country}: ${p.count} events${p.sim ? ' (simulated)' : ''}`; markers.add(head); heads.push(head)
        const a = toVec(p.lat, p.lon, 1.01), b = toVec(HP.lat, HP.lon, 1.01), ang = a.angleTo(b)
        if (ang < 0.03) continue
        const mid = a.clone().add(b); if (mid.lengthSq() < 1e-6) mid.set(0, 1, 0)
        const curve = new THREE.QuadraticBezierCurve3(a, mid.normalize().multiplyScalar(1.1 + (0.9 * ang) / Math.PI), b)
        markers.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(48)), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 })))
        const comet = new THREE.Mesh(new THREE.SphereGeometry(0.008, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffffff })); markers.add(comet)
        comets.push({ m: comet, c: curve, t: Math.random() })
      }
    }

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true; controls.enablePan = false; controls.minDistance = 1.6; controls.maxDistance = 5
    controls.autoRotate = true; controls.autoRotateSpeed = 0.6
    let resume = 0
    controls.addEventListener('start', () => { controls.autoRotate = false; window.clearTimeout(resume) })
    controls.addEventListener('end', () => { resume = window.setTimeout(() => { controls.autoRotate = true }, 3000) })

    const ray = new THREE.Raycaster(), ndc = new THREE.Vector2()
    const onMove = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, camera)
      const hit = ray.intersectObjects([globe, ...heads], false)[0]   // globe first: hides markers on the far side
      setTip(hit && hit.object !== globe ? { x: e.clientX - r.left, y: e.clientY - r.top, text: String(hit.object.userData.label) } : null)
    }
    renderer.domElement.addEventListener('pointermove', onMove)
    renderer.domElement.addEventListener('pointerleave', () => setTip(null))

    const ro = new ResizeObserver(() => { renderer.setSize(width(), HEIGHT); camera.aspect = width() / HEIGHT; camera.updateProjectionMatrix() }); ro.observe(el)
    const clock = new THREE.Clock(); let raf = 0
    const tick = () => {
      const dt = clock.getDelta()
      for (const c of comets) { c.t = (c.t + dt * 0.3) % 1; c.m.position.copy(c.c.getPoint(c.t)) }
      controls.update(); renderer.render(scene, camera); raf = requestAnimationFrame(tick)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf); window.clearTimeout(resume); ro.disconnect(); controls.dispose(); disposeMarkers()
      scene.traverse(o => { const m = o as THREE.Mesh; m.geometry?.dispose() })
      material.map?.dispose(); material.emissiveMap?.dispose(); material.bumpMap?.dispose(); material.dispose()
      renderer.dispose(); renderer.domElement.remove(); setPointsRef.current = () => undefined
    }
  }, [onFail])

  useEffect(() => { setPointsRef.current(points) }, [points])

  return (<div className="relative w-full overflow-hidden rounded bg-[#02040a]" style={{ height: HEIGHT }}>
    <div ref={host} className="h-full w-full" />
    {tip && <div className="pointer-events-none absolute rounded bg-black/80 px-2 py-1 text-xs text-slate-100" style={{ left: tip.x + 12, top: tip.y + 12 }}>{tip.text}</div>}
    <div className="pointer-events-none absolute bottom-2 left-3 text-[10px] text-slate-500">drag to rotate · scroll to zoom · Earth imagery: NASA</div>
  </div>)
}
