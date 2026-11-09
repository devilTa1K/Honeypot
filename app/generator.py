"""Deterministic fallback company generator. All data is synthetic."""
import random
from pydantic import BaseModel

class Employee(BaseModel):
    name: str; email: str; dept: str; title: str

class Company(BaseModel):
    name: str; industry: str; size: int; domain: str
    employees: list[Employee]; aws_key_id: str; aws_secret: str; repos: list[str]

FIRST = ["Aarav","Maya","Liam","Sofia","Noah","Priya","Ethan","Zara","Kenji","Elena"]
LAST = ["Patil","Novak","Okafor","Tanaka","Silva","Meyer","Rao","Khan","Costa","Berg"]
DEPTS = {"Engineering":"Software Engineer","Finance":"Accountant","HR":"HR Partner","IT":"SysAdmin","Sales":"Account Exec"}

def generate_company(name: str, industry: str, size: int, seed: int | None = None) -> Company:
    rng = random.Random(seed if seed is not None else f"{name}|{industry}|{size}")
    domain = name.lower().replace(" ", "") + ".example"   # .example is reserved, never resolvable
    emps = []
    for _ in range(min(max(size, 5), 200)):
        f, l = rng.choice(FIRST), rng.choice(LAST)
        d = rng.choice(list(DEPTS))
        emps.append(Employee(name=f"{f} {l}", email=f"{f}.{l}@{domain}".lower(), dept=d, title=DEPTS[d]))
    # Random decoy creds in AWS-like format; never issued by AWS
    key = "AKIA" + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(16))
    sec = "".join(rng.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(40))
    return Company(name=name, industry=industry, size=size, domain=domain, employees=emps,
                   aws_key_id=key, aws_secret=sec, repos=[f"{name.lower().replace(' ','-')}-{r}" for r in ("api","infra","billing")])

def repo_files(c: Company) -> dict[str, dict[str, str]]:
    """Synthetic source repositories served by the decoy. Credentials are the company's random decoy keys."""
    api, infra, billing = c.repos
    return {
        api: {"README.md": f"# {c.name} API\nInternal service. Contact platform@{c.domain}.\n",
              "config.py": f"AWS_ACCESS_KEY_ID = '{c.aws_key_id}'\nAWS_SECRET_ACCESS_KEY = '{c.aws_secret}'\nDB_URL = 'postgresql://svc_api:CHANGEME@db.internal.{c.domain}:5432/app'\n"},
        infra: {"deploy.sh": f"#!/bin/sh\n# deploy to prod\nssh deploy@bastion.{c.domain} './release.sh'\n",
                "terraform/main.tf": f"provider \"aws\" {{ region = \"us-east-1\" }}\n# {c.name} production VPC\n"},
        billing: {"invoices.py": "def total(items):\n    return sum(i['amount'] for i in items)\n"}}
