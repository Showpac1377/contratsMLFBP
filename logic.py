"""Règles de ligue, calculs de masse salariale et lecture des contrats PuckPedia."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

POS = {"F": "Attaquants", "D": "Défenseurs", "G": "Gardiens"}
POS_ICON = {"F": "🔵", "D": "🟠", "G": "🟡"}


# ---------- saisons / montants ----------
def lab(y: int) -> str:
    y = int(y)
    return f"{y}-{(y + 1) % 100:02d}"


def seasons(team: dict) -> list[int]:
    return [team["currentSeason"] + i for i in range(team["nSeasons"])]


def fmt(n, full: bool = False) -> str:
    if n is None or n == "":
        return ""
    n = float(n)
    if full:
        return f"{n:,.0f}".replace(",", " ")
    if abs(n) >= 1e6:
        s = f"{n / 1e6:.3f}".rstrip("0").rstrip(".")
        return s.replace(".", ",") + " M"
    return f"{round(n / 1e3):,}".replace(",", " ") + " k"


def parse_amt(v) -> int | None:
    """Accepte 4500000, 4,5M, 875k, 4.5 (=millions)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if v != v or v <= 0:  # NaN
            return None
        return int(round(v * 1e6)) if v < 1000 else int(round(v))
    s = str(v).strip().lower().replace(" ", "").replace(" ", "").replace("$", "").replace(",", ".")
    if not s:
        return None
    mult = 1
    if s.endswith("m"):
        mult, s = 1_000_000, s[:-1]
    elif s.endswith("k"):
        mult, s = 1_000, s[:-1]
    try:
        n = float(s)
    except ValueError:
        return None
    if mult == 1 and n < 1000:
        n *= 1_000_000
    return int(round(n * mult)) if n > 0 else None


# ---------- joueurs ----------
def years(p: dict) -> list[int]:
    return sorted(int(k) for k, c in (p.get("contract") or {}).items() if c and c.get("a"))


def last_year(p: dict) -> int | None:
    y = years(p)
    return y[-1] if y else None


def age_on(p: dict, d: date) -> int | None:
    b = p.get("birth")
    if not b:
        return None
    try:
        b = date.fromisoformat(b)
    except ValueError:
        return None
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def age_season(p: dict, season: int) -> int | None:
    """Âge au 1er octobre de l'année de début de la saison (ex. 2026 -> 1er oct. 2026)."""
    return age_on(p, date(int(season), 10, 1))


def age_resign(p: dict, closing: int) -> int | None:
    """Re-signature à la fin de la saison `closing` (ex. 2026-27 -> contrats dès 2027-28) : âge au 1er oct. 2026."""
    return age_season(p, closing)


def max_len(age: int | None) -> int:
    if age is None:
        return 4
    if age <= 20:
        return 3
    if age <= 22:
        return 2
    if age <= 29:
        return 3
    return 4  # 3 + 1 gratuite


def counted_years(age: int | None, n: int) -> int:
    return min(n, 3) if (age is not None and age >= 30) else n


def mass_by(players: list[dict], seas: list[int]) -> dict[int, int]:
    out = {y: 0 for y in seas}
    for p in players:
        for y in seas:
            c = p["contract"].get(str(y))
            if c and c.get("a"):
                out[y] += c["a"]
    return out


def max_sal(p: dict, seas: list[int]) -> int:
    return max([p["contract"].get(str(y), {}).get("a") or 0 for y in seas] or [0])


# ---------- re-signatures ----------
def resign_calc(players: list[dict], rows: list[dict], closing: int, rules: dict) -> dict:
    """rows: [{id, sign, created, years, amount}] -> compteurs + erreurs + ajout de masse."""
    by = {p["id"]: p for p in players}
    used = yrs = 0
    errs: list[str] = []
    add: dict[int, int] = {}
    for r in rows:
        p = by.get(r["id"])
        if not p or not r.get("sign"):
            continue
        a = age_resign(p, closing)
        ml = max_len(a)
        n = int(r.get("years") or 0)
        amt = parse_amt(r.get("amount"))
        if n < 1:
            errs.append(f"{p['name']} : durée manquante")
        if n > ml:
            errs.append(f"{p['name']} : max {ml} an(s) à {a} ans")
        if not amt:
            errs.append(f"{p['name']} : cap hit manquant")
        if not r.get("created"):
            used += 1
            yrs += counted_years(a, n)
        for k in range(1, n + 1):
            add[closing + k] = add.get(closing + k, 0) + (amt or 0)
    if used > rules["maxResign"]:
        errs.append(f"Trop de re-signatures : {used}/{rules['maxResign']}")
    if yrs > rules["maxYears"]:
        errs.append(f"Trop d'années : {yrs}/{rules['maxYears']}")
    return {"used": used, "yrs": yrs, "errs": errs, "add": add}


# ---------- PuckPedia ----------
def pp_url(name: str) -> str:
    s = unicodedata.normalize("NFD", name or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"https://puckpedia.com/player/{s}"


_AMT = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+)")


def _amts(s: str) -> list[int]:
    return [int(m.replace(",", "")) for m in _AMT.findall(s)]


def _cells(row: str) -> list[int | None]:
    """Cellules d'une ligne de tableau : montant, ou None pour « - »."""
    if "|" not in row:
        return list(_amts(row))
    out = []
    for cell in row.split("|"):
        c = cell.strip()
        if not c:
            continue
        a = _amts(c)
        if a:
            out.append(a[0])
        elif c in {"-", "—", "–", "$0"}:
            out.append(None)
        else:
            break  # ex. « UFA no QO » : fin du contrat
    return out


def _per_season(seg: str, row: str = "cap hit") -> dict[int, int] | None:
    labs: list[int] = []
    for m in re.finditer(r"(?:^|[^\d])(20\d{2})\s*-\s*(\d{2})(?!\d)", seg):
        y = int(m.group(1))
        if (y + 1) % 100 == int(m.group(2)) and y not in labs:
            labs.append(y)
    if not labs:
        return None
    first = re.search(r"20\d{2}\s*-\s*\d{2}(?!\d)", seg)
    rest = seg[first.start():]
    pat = r"\s*".join(re.escape(w) for w in row.split())
    cm = re.search(r"(?:^|\n)\s*" + pat + r"\b([^\n]*)", rest, re.I)
    if not cm:
        return None
    a = _cells(cm.group(1))
    if not any(a):
        return None
    return {labs[i]: a[i] for i in range(min(len(a), len(labs))) if a[i]}


def parse_puckpedia(txt: str, basis: str = "cap") -> list[dict]:
    """Texte copié d'une page joueur PuckPedia -> contrats {label, cap, seasons{an: montant}, note}.
    basis="cap" : CAP HIT par saison · basis="total" : TOTAL SALARY par saison."""
    row = "total salary" if basis == "total" else "cap hit"
    txt = (txt or "").replace("\r", "").replace(" ", " ").replace("\t", " | ")
    heads = [
        (int(m.group(1)), int(m.group(2)), m.start(), m.end())
        for m in re.finditer(r"(?:^|\n)\s*(20\d{2})\s*[-–]\s*(20\d{2})\s*(?=\n)", txt)
    ]
    out = []
    for k, (s, e, _i, end) in enumerate(heads):
        seg = txt[end: heads[k + 1][2] if k + 1 < len(heads) else len(txt)]
        ch = re.search(r"cap\s*hit\s*:?\s*\|?\s*\$\s?(\d{1,3}(?:,\d{3})+)", seg, re.I)
        if not ch or e <= s:
            continue
        cap = int(ch.group(1).replace(",", ""))
        tm = re.search(r"([A-Za-z\- ]*Contract)", seg[:200])
        ps = _per_season(seg, row)
        note = ""
        if not ps:
            ps = {y: cap for y in range(s, e)}
            if basis == "total":
                note = "Salaire total introuvable : cap hit utilisé — vérifie."
        out.append({"label": f"{s}-{e}" + (f" · {tm.group(1).strip()}" if tm else ""), "cap": cap, "seasons": ps,
                    "note": note})
    if not out:
        ps = _per_season(txt, row)
        if ps:
            ks = sorted(ps)
            out.append({"label": f"Tableau collé ({lab(ks[0])} → {lab(ks[-1])})", "cap": ps[ks[0]], "seasons": ps, "note": ""})
    return out
