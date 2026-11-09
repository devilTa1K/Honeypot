"""Fake shell. Pure in-memory: never executes commands, touches the real filesystem, or opens network connections."""
import posixpath, shlex

class FakeShell:
    def __init__(self, host: str = "srv01"):
        self.cwd, self.host = "/root", host
        self.files = {"/etc/passwd": "root:x:0:0:root:/root:/bin/bash\nsvc-deploy:x:1001:1001::/home/svc-deploy:/bin/bash\n",
                      "/etc/hostname": host + "\n", "/root/notes.txt": "TODO: rotate deploy keys\n"}
        self.dirs = {"/", "/root", "/etc", "/tmp", "/home", "/home/svc-deploy", "/var"}

    def prompt(self) -> str:
        return f"root@{self.host}:{'~' if self.cwd == '/root' else self.cwd}# "

    def _p(self, p: str) -> str:
        return posixpath.normpath(p if p.startswith("/") else posixpath.join(self.cwd, p))

    def _ls(self, d: str) -> str:
        names = {posixpath.basename(x) for x in list(self.files) + list(self.dirs) if x != d and posixpath.dirname(x) == d}
        return "\n".join(sorted(names)) + ("\n" if names else "")

    def run(self, line: str) -> tuple[str, bool]:
        """Returns (output, should_exit). Supports ';' and '&&' chaining."""
        out = ""
        for part in line.replace("&&", ";").split(";"):
            try:
                a = shlex.split(part)
            except ValueError:
                return out + "bash: syntax error: unexpected end of file\n", False
            if not a:
                continue
            c, args = a[0], a[1:]
            if c in ("exit", "logout"): return out, True
            elif c == "pwd": out += self.cwd + "\n"
            elif c == "whoami": out += "root\n"
            elif c == "id": out += "uid=0(root) gid=0(root) groups=0(root)\n"
            elif c == "hostname": out += self.host + "\n"
            elif c == "uname": out += "Linux " + self.host + " 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux\n" if "-a" in args else "Linux\n"
            elif c == "echo": out += " ".join(args) + "\n"
            elif c == "ls":
                d = self._p(args[-1]) if args and not args[-1].startswith("-") else self.cwd
                out += self._ls(d) if d in self.dirs else f"ls: cannot access '{d}': No such file or directory\n"
            elif c == "cd":
                d = self._p(args[0]) if args else "/root"
                if d in self.dirs: self.cwd = d
                else: out += f"bash: cd: {args[0]}: No such file or directory\n"
            elif c == "cat":
                for f in args:
                    p = self._p(f)
                    out += self.files.get(p) or (f"cat: {f}: No such file or directory\n" if p not in self.files else "")
            elif c == "ps": out += "  PID TTY          TIME CMD\n    1 ?        00:00:02 systemd\n  412 ?        00:00:00 sshd\n  977 pts/0    00:00:00 bash\n"
            elif c in ("ifconfig", "ip"): out += "eth0: inet 10.0.2.15  netmask 255.255.255.0  broadcast 10.0.2.255\n"
            elif c in ("wget", "curl"): out += "Connecting... failed: Temporary failure in name resolution.\n"
            elif c in ("chmod", "chown", "chgrp", "kill", "export", "clear", "nohup", "unset"): pass          # silent success, no real effect
            elif c == "mkdir":
                for a_ in args:
                    if not a_.startswith("-"): self.dirs.add(self._p(a_))
            elif c == "touch":
                for a_ in args: self.files.setdefault(self._p(a_), "")
            elif c == "rm":
                for a_ in args:
                    if not a_.startswith("-"): self.files.pop(self._p(a_), None)   # only touches the in-memory fake FS
            elif c == "uptime": out += " 11:02:41 up 41 days,  3:12,  1 user,  load average: 0.08, 0.03, 0.01\n"
            elif c == "df": out += "Filesystem     1K-blocks    Used Available Use% Mounted on\n/dev/sda1       41152736 9876544  29172664  26% /\n"
            elif c == "free": out += "              total        used        free\nMem:        4040864     812332    2310004\n"
            elif c in ("sudo", "su"): out += f"{c}: authentication failure\n"
            else: out += f"bash: {c}: command not found\n"
        return out[:4000], False
