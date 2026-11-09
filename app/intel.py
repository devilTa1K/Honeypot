"""Threat-intelligence aggregation over captured events (pure function; attempts only, never successes)."""
import ipaddress, re
from collections import Counter
from .analyst import TACTICS, risk_of
_URL, _IP, _PW = re.compile(r"https?://[^\s'\"<>]+"), re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), re.compile(r"^password=(.*) accepted=(True|False)$", re.S)

def _public(ip: str) -> bool:
    try: return ipaddress.ip_address(ip).is_global
    except ValueError: return False

def build(events: list[dict], top: int = 10) -> dict:
    by_ip: dict[str, dict] = {}; by_sess: dict[str, dict] = {}
    creds, cmds, paths, tactics, iocs = Counter(), Counter(), Counter(), Counter(), Counter()
    for e in events:
        i = by_ip.setdefault(e["ip"], {"ip": e["ip"], "count": 0, "labels": set(), "first": e["ts"], "last": e["ts"], "sessions": set()})
        i["count"] += 1; i["labels"].add(e["label"]); i["first"], i["last"] = min(i["first"], e["ts"]), max(i["last"], e["ts"]); i["sessions"].add(e["session"])
        s = by_sess.setdefault(e["session"], {"session": e["session"], "ip": e["ip"], "events": 0, "stages": set(), "last": e["ts"]})
        s["events"] += 1; s["stages"].add(e["label"]); s["last"] = max(s["last"], e["ts"])
        if e["label"] in TACTICS: tactics[TACTICS[e["label"]]] += 1
        m = e["method"]
        if m == "SSH-AUTH":
            mt = _PW.match(e["body"])
            if mt: creds[(e["path"], mt.group(1), mt.group(2) == "True")] += 1
        elif m == "SSH":
            cmds[e["path"]] += 1
            for u in _URL.findall(e["path"]): iocs[("url", u)] += 1
            for ip in _IP.findall(e["path"]):
                if _public(ip): iocs[("ip", ip)] += 1
        else:
            paths[e["path"]] += 1
            for u in _URL.findall(e["body"]): iocs[("url", u)] += 1
    return {
        "totals": {"events": len(events), "sources": len(by_ip), "sessions": len(by_sess)},
        "top_ips": [{**v, "labels": sorted(v["labels"]), "sessions": len(v["sessions"])} for v in sorted(by_ip.values(), key=lambda x: -x["count"])[:top]],
        "credentials": [{"username": u, "password": p, "accepted": a, "count": n} for (u, p, a), n in creds.most_common(top)],
        "commands": [{"command": c, "count": n} for c, n in cmds.most_common(top)],
        "paths": [{"path": p, "count": n} for p, n in paths.most_common(top)],
        "tactics": [{"tactic": t, "count": n} for t, n in tactics.most_common()],
        "iocs": [{"kind": k, "value": v, "count": n} for (k, v), n in iocs.most_common(top)],
        "sessions": [{**s, "stages": sorted(s["stages"]), "risk": risk_of(s["stages"])} for s in sorted(by_sess.values(), key=lambda x: -x["last"])[:25]]}
