"""Rule-based classifier. Labels *attempts* only; never claims successful exploitation."""
import re
RULES = [
    ("exploitation_attempt", re.compile(r"(\.\./|<script|union\s+select|;\s*(cat|wget|curl)|\$\(|%00)", re.I)),
    ("privilege_escalation_attempt", re.compile(r"(sudo|/etc/shadow|chmod\s+[0-7]*7|setuid)", re.I)),
    ("credential_probing", re.compile(r"(/login|/signin|/auth|password=|/admin-panel|/wp-login|/phpmyadmin|/console)", re.I)),
    ("data_discovery_attempt", re.compile(r"(\.env|\.git|/repos|/backup|/api/aws|\.sql|\.bak|dump|/api/(customers|users)|/admin/export|credentials)", re.I)),
    ("enumeration", re.compile(r"(/api/|/admin|/wiki|/directory|/employees)", re.I)),
    ("reconnaissance", re.compile(r"(robots\.txt|sitemap|favicon|^/$|\.well-known|/server-status)", re.I)),
]
def classify(path: str, body: str = "") -> str:
    text = f"{path} {body}"
    for label, rx in RULES:
        if rx.search(text):
            return label
    return "reconnaissance"

CMD_RULES = [
    ("privilege_escalation_attempt", re.compile(r"(\bsudo\b|\bsu\s|/etc/shadow|\bsetuid\b|chmod\s+[0-7]*[4-7][0-7]{2}\b)", re.I)),
    ("exploitation_attempt", re.compile(r"(\bwget\b|\bcurl\b|\btftp\b|\bnc\b|\bncat\b|bash\s+-i|/dev/tcp|base64\s+-d|chmod\s+\+x|python\d?\s+-c|perl\s+-e|(^|\s)\./\S+)", re.I)),
    ("data_discovery_attempt", re.compile(r"(/etc/passwd|\.ssh|\.env|history|id_rsa|aws|credentials|\bcat\b)", re.I)),
]
def classify_command(cmd: str) -> str:
    """Shell-command classifier. Labels what was *attempted* in a fake shell."""
    for label, rx in CMD_RULES:
        if rx.search(cmd):
            return label
    return "enumeration"
