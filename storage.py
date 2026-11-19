"""Lecture / écriture des données : GitHub (Streamlit Cloud) ou fichier local."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import requests
import streamlit as st

SEED = Path(__file__).parent / "data" / "contrats.json"
API = "https://api.github.com"


class Conflict(Exception):
    pass


def _cfg() -> dict | None:
    try:
        g = st.secrets.get("github")
    except Exception:  # pas de secrets.toml en local
        return None
    if not g or not g.get("token") or not g.get("repo"):
        return None
    return {
        "token": g["token"],
        "repo": g["repo"],
        "branch": g.get("branch", "data"),
        "path": g.get("path", "data/contrats.json"),
    }


def mode() -> str:
    c = _cfg()
    return f"GitHub · {c['repo']} (branche {c['branch']})" if c else "Fichier local"


def _h(c):
    return {"Authorization": f"Bearer {c['token']}", "Accept": "application/vnd.github+json"}


def _ensure_branch(c):
    r = requests.get(f"{API}/repos/{c['repo']}/branches/{c['branch']}", headers=_h(c), timeout=20)
    if r.status_code == 200:
        return
    repo = requests.get(f"{API}/repos/{c['repo']}", headers=_h(c), timeout=20)
    repo.raise_for_status()
    default = repo.json()["default_branch"]
    ref = requests.get(f"{API}/repos/{c['repo']}/git/ref/heads/{default}", headers=_h(c), timeout=20)
    ref.raise_for_status()
    requests.post(
        f"{API}/repos/{c['repo']}/git/refs",
        headers=_h(c),
        json={"ref": f"refs/heads/{c['branch']}", "sha": ref.json()["object"]["sha"]},
        timeout=20,
    ).raise_for_status()


def load() -> tuple[dict, str | None]:
    """Retourne (données, sha). sha=None en mode local."""
    c = _cfg()
    if not c:
        return json.loads(SEED.read_text(encoding="utf-8")), None
    _ensure_branch(c)
    r = requests.get(
        f"{API}/repos/{c['repo']}/contents/{c['path']}",
        headers=_h(c), params={"ref": c["branch"]}, timeout=20,
    )
    if r.status_code == 404:  # premier lancement : on part du fichier de départ
        data = json.loads(SEED.read_text(encoding="utf-8"))
        return data, save(data, None, "Création du fichier de contrats")
    r.raise_for_status()
    j = r.json()
    return json.loads(base64.b64decode(j["content"]).decode("utf-8")), j["sha"]


def save(data: dict, sha: str | None, message: str = "Mise à jour des contrats") -> str | None:
    """Enregistre et retourne le nouveau sha. Lève Conflict si le fichier a changé ailleurs."""
    body = json.dumps(data, ensure_ascii=False, indent=1)
    c = _cfg()
    if not c:
        SEED.write_text(body, encoding="utf-8")
        return None
    payload = {
        "message": message,
        "content": base64.b64encode(body.encode("utf-8")).decode(),
        "branch": c["branch"],
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(f"{API}/repos/{c['repo']}/contents/{c['path']}", headers=_h(c), json=payload, timeout=30)
    if r.status_code in (409, 422) and sha:
        raise Conflict(r.text)
    r.raise_for_status()
    return r.json()["content"]["sha"]
