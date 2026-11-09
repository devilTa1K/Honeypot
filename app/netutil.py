import ipaddress, os
TRUSTED = [ipaddress.ip_network(n) for n in os.environ.get(
    "HIAB_TRUSTED_PROXIES", "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16").split(",")]

def trusted(ip: str) -> bool:
    try:
        return any(ipaddress.ip_address(ip) in n for n in TRUSTED)
    except ValueError:
        return False
