"""GeoIP lookup. Only public IPs are located, using a MaxMind-format City database you supply via HIAB_GEOIP_DB (not bundled: licence)."""
import ipaddress, os
_reader = None

def reader():
    global _reader
    p = os.environ.get("HIAB_GEOIP_DB")
    if _reader is None and p and os.path.exists(p):
        import geoip2.database
        _reader = geoip2.database.Reader(p)
    return _reader

def locate(ip: str, rd=None) -> dict | None:
    try:
        if not ipaddress.ip_address(ip).is_global: return None
    except ValueError:
        return None
    rd = rd or reader()
    if rd is None: return None
    try:
        r = rd.city(ip)
        if r.location.latitude is None or r.location.longitude is None: return None
        return {"lat": r.location.latitude, "lon": r.location.longitude, "country": r.country.iso_code or "??"}
    except Exception:
        return None

def summarize(events: list[dict], rd=None) -> dict:
    rd = rd or reader()
    by_ip = {ip: (locate(ip, rd) if rd else None) for ip in {e["ip"] for e in events}}
    pts: dict[tuple, int] = {}
    for e in events:
        loc = by_ip[e["ip"]]
        if loc: k = (round(loc["lat"], 1), round(loc["lon"], 1), loc["country"]); pts[k] = pts.get(k, 0) + 1
    return {"geoip_enabled": rd is not None, "unlocated_ips": sum(1 for v in by_ip.values() if v is None),
            "points": [{"lat": a, "lon": b, "country": c, "count": n} for (a, b, c), n in pts.items()]}
