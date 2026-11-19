"""Contrats — FBP Islanders & ML Canadiens (Streamlit)."""
from __future__ import annotations

import copy
import html
import json
import uuid
from datetime import date

import pandas as pd
import streamlit as st

import storage
from logic import (POS, POS_ICON, age_resign, age_season, fmt, lab, last_year, mass_by,
                   max_len, max_sal, parse_amt, parse_puckpedia, pp_url, resign_calc, seasons, years)

st.set_page_config(page_title="Contrats — FBP & ML", page_icon="🏒", layout="wide")
ss = st.session_state

# ====================================================================== état
if "root" not in ss:
    try:
        ss.root, ss.sha = storage.load()
    except Exception as e:  # noqa: BLE001
        st.error(f"Impossible de charger les données : {e}")
        st.stop()
    ss.dirty, ss.undo, ss.scen, ss.ver = False, [], None, 0
    ss.team_id = ss.root.get("active") or ss.root["teams"][0]["id"]
    for t in ss.root["teams"]:
        t.setdefault("scenarios", []); t.setdefault("history", []); t.setdefault("players", [])


def team() -> dict:
    for t in ss.root["teams"]:
        if t["id"] == ss.team_id:
            return t
    ss.team_id = ss.root["teams"][0]["id"]
    return ss.root["teams"][0]


def view() -> dict:
    """Alignement affiché : le réel, ou le scénario sélectionné."""
    T = team()
    if ss.scen:
        for s in T["scenarios"]:
            if s["id"] == ss.scen:
                return s
        ss.scen = None
    return T


def snapshot():
    ss.undo.append(json.dumps(ss.root))
    ss.undo = ss.undo[-40:]
    ss.dirty = True


def bump():
    ss.ver += 1


def _d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def uid(prefix="p") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


# ====================================================================== droits
try:
    PASSWORD = st.secrets.get("APP_PASSWORD")
except Exception:  # noqa: BLE001
    PASSWORD = None
can_edit = (not PASSWORD) or ss.get("auth", False)

# ====================================================================== style
st.markdown("""
<style>
:root{--navy:#001a4a;--blue:#003087;--orange:#f47d30;--zebra:#ebf1fa}
.block-container{padding-top:1.6rem;max-width:1500px}
.ct-wrap{overflow-x:auto;border:1px solid #d6dde9;border-radius:10px;margin-top:.4rem}
table.ct{border-collapse:collapse;width:100%;min-width:980px;font-size:13.5px}
table.ct th,table.ct td{padding:5px 8px;border-bottom:1px solid #e6ebf3;text-align:right;white-space:nowrap}
table.ct th{background:var(--blue);color:#fff;font-weight:600;font-size:12px}
table.ct .l{text-align:left}
table.ct td.nm{position:sticky;left:0;background:inherit;z-index:1}
table.ct tr.pl{background:#fff}table.ct tr.pl:nth-child(even){background:var(--zebra)}
table.ct tr.grp td{color:#fff;font-weight:700;text-align:left;font-size:15px}
tr.grp.F td{background:var(--blue)}tr.grp.D td{background:var(--orange)}tr.grp.G td{background:var(--navy)}tr.grp.X td{background:#7a8499}
table.ct tr.sub td{font-weight:700;background:#eef2f9;border-bottom:2px solid #d6dde9}
table.ct tr.tot td{background:var(--navy);color:#fff;font-weight:700}
table.ct tr.cap td{background:var(--blue);color:#fff}
table.ct td.r{background:var(--orange)!important;color:#fff;font-weight:600}
table.ct td.exp span{font-size:11px;color:#6b7690;border:1px dashed #b7c0d3;border-radius:5px;padding:0 6px}
.tag{font-size:10px;font-weight:700;border-radius:4px;padding:1px 5px;margin-left:5px}
.tag.ex{background:#d9f2e2;color:#1b7a3d}.tag.warn{background:#ffe6c7;color:#a35200}
.meta{font-size:11px;color:#6b7690;margin-left:5px}
.neg{color:#c62828!important}.pos{color:#1b7a3d!important}
.simbar{background:repeating-linear-gradient(135deg,#fff3e9,#fff3e9 12px,#ffe9d8 12px,#ffe9d8 24px);border:2px solid var(--orange);border-radius:10px;padding:8px 12px;margin-bottom:8px}
</style>""", unsafe_allow_html=True)

# ====================================================================== barre latérale
with st.sidebar:
    st.markdown("## 🏒 Contrats")
    ids = [t["id"] for t in ss.root["teams"]]
    names = {t["id"]: t["team"] for t in ss.root["teams"]}
    pick = st.radio("Équipe", ids, index=ids.index(ss.team_id) if ss.team_id in ids else 0,
                    format_func=lambda i: names[i], horizontal=True)
    if pick != ss.team_id:
        ss.team_id, ss.scen = pick, None
        bump()
        st.rerun()
    T = team()

    opts = [None] + [s["id"] for s in T["scenarios"]]
    snames = {s["id"]: s["name"] for s in T["scenarios"]}
    sel = st.selectbox("Affichage", opts, index=opts.index(ss.scen) if ss.scen in opts else 0,
                       format_func=lambda i: "🏒 Alignement réel" if i is None else f"🧪 {snames[i]}")
    if sel != ss.scen:
        ss.scen = sel
        bump()
        st.rerun()

    if PASSWORD and not ss.get("auth"):
        pw = st.text_input("Mot de passe (pour modifier)", type="password")
        if pw:
            if pw == PASSWORD:
                ss.auth = True
                st.rerun()
            st.error("Mot de passe incorrect")

    if can_edit:
        with st.expander("🧪 Scénarios", expanded=bool(ss.scen)):
            nn = st.text_input("Nom du nouveau scénario", placeholder=f"Scénario {len(T['scenarios']) + 1}")
            if st.button("＋ Créer (copie de l'affichage)", width="stretch"):
                src = view()
                snapshot()
                s = {"id": uid("s"), "name": nn.strip() or f"Scénario {len(T['scenarios']) + 1}",
                     "players": copy.deepcopy(src["players"]), "history": copy.deepcopy(src.get("history", []))}
                T["scenarios"].append(s)
                ss.scen = s["id"]
                bump()
                st.rerun()
            if ss.scen:
                sc = view()
                rn = st.text_input("Renommer", value=sc["name"], key=f"rn_{sc['id']}")
                if rn.strip() and rn.strip() != sc["name"]:
                    snapshot(); sc["name"] = rn.strip(); st.rerun()
                c1, c2 = st.columns(2)
                if c1.button("Dupliquer", width="stretch"):
                    snapshot()
                    s = {"id": uid("s"), "name": sc["name"] + " (copie)",
                         "players": copy.deepcopy(sc["players"]), "history": copy.deepcopy(sc.get("history", []))}
                    T["scenarios"].append(s); ss.scen = s["id"]; bump(); st.rerun()
                if c2.button("Supprimer", width="stretch"):
                    snapshot()
                    T["scenarios"] = [x for x in T["scenarios"] if x["id"] != sc["id"]]
                    ss.scen = None; bump(); st.rerun()
                ok = st.checkbox("Je confirme : remplacer l'alignement réel")
                if st.button("✅ Appliquer au réel", type="primary", disabled=not ok, width="stretch"):
                    snapshot()
                    T["players"] = copy.deepcopy(sc["players"]); T["history"] = copy.deepcopy(sc.get("history", []))
                    ss.scen = None; bump()
                    st.toast(f"« {sc['name']} » appliqué au réel — pense à enregistrer.")
                    st.rerun()

        st.divider()
        if st.button("💾 Enregistrer" + (" *" if ss.dirty else ""), type="primary" if ss.dirty else "secondary",
                     width="stretch", disabled=not ss.dirty):
            try:
                ss.root["active"] = ss.team_id
                ss.sha = storage.save(ss.root, ss.sha, f"Contrats — {date.today().isoformat()}")
                ss.dirty = False
                st.toast("Enregistré ✔")
            except storage.Conflict:
                st.error("Les données ont été modifiées ailleurs (autre onglet/appareil). Clique « Recharger » "
                         "puis refais tes changements.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Échec de l'enregistrement : {e}")
        c1, c2 = st.columns(2)
        if c1.button("↶ Annuler", disabled=not ss.undo, width="stretch"):
            ss.root = json.loads(ss.undo.pop()); ss.dirty = True; bump(); st.rerun()
        if c2.button("⟳ Recharger", width="stretch", help="Abandonne les changements non enregistrés"):
            for k in ("root", "sha"):
                ss.pop(k, None)
            st.rerun()
        if ss.dirty:
            st.warning("Changements non enregistrés.")
    st.caption(f"Stockage : {storage.mode()}")

T, V = team(), view()
R = T["rules"]
SZ = seasons(T)
BASIS = T.get("salaryBasis", "cap")
AMT = "Cap hit" if BASIS == "cap" else "Salaire total"


def cap_of(y):
    v = T.get("caps", {}).get(str(y))
    return int(v) if v else None


# ====================================================================== en-tête
st.title(f"{T['team']} — Contrats")
st.caption(f"Saison en cours : {lab(T['currentSeason'])} · {len(V['players'])} joueurs · montants = {AMT.lower()}"
           + (" · 🧪 SIMULATION" if ss.scen else "") + ("" if can_edit else " · lecture seule"))

if ss.scen:
    Rm, Sm = mass_by(T["players"], SZ), mass_by(V["players"], SZ)
    st.markdown(f'<div class="simbar">🧪 <b>Simulation : {html.escape(V["name"])}</b> — '
                f'rien ici ne touche l\'alignement réel.</div>', unsafe_allow_html=True)
    cmp = pd.DataFrame(
        {lab(y): [fmt(Rm[y]), fmt(Sm[y]),
                  "—" if Sm[y] == Rm[y] else ("+" if Sm[y] > Rm[y] else "−") + fmt(abs(Sm[y] - Rm[y])),
                  "—" if cap_of(y) is None else fmt(cap_of(y) - Sm[y])] for y in SZ},
        index=["Réel", "Scénario", "Écart", "Espace (scénario)"])
    st.dataframe(cmp, width="stretch")
    rid = {p["id"]: p for p in T["players"]}
    sid = {p["id"] for p in V["players"]}
    add = [p["name"] for p in V["players"] if p["id"] not in rid]
    rem = [p["name"] for p in T["players"] if p["id"] not in sid]
    chg = [p["name"] for p in V["players"] if p["id"] in rid and rid[p["id"]]["contract"] != p["contract"]]
    parts = ([f"**Ajoutés :** {', '.join(add)}"] if add else []) + ([f"**Retirés :** {', '.join(rem)}"] if rem else []) \
        + ([f"**Contrats modifiés :** {', '.join(chg)}"] if chg else [])
    st.markdown(" · ".join(parts) if parts else "_Aucune différence avec le réel pour l'instant._")

# ====================================================================== fiche joueur
def open_fiche(pid: str | None):
    """Ouvre la fiche d'un joueur (pid) ou d'un nouveau joueur (None)."""
    if pid:
        p = next((x for x in view()["players"] if x["id"] == pid), None)
        if not p:
            return
        ss.fd = copy.deepcopy(p)
    else:
        ss.fd = {"id": uid(), "name": "", "pos": "F", "birth": "", "ppm": None, "notes": "", "contract": {}}
    ss.fdv = ss.get("fdv", 0) + 1
    ss.fd_pp = None
    ss.open_fiche = True


def close_fiche():
    ss.open_fiche = False
    ss.fd = None
    bump()  # désélectionne la ligne cliquée


@st.dialog("Fiche joueur", width="large", on_dismiss=close_fiche)
def fiche():
    T_, V_ = team(), view()
    d, v = ss.fd, ss.fdv
    cur_ = T_["currentSeason"]
    amt_lbl = "cap hit" if T_.get("salaryBasis", "cap") == "cap" else "salaire total"

    def k(s):
        return f"fd_{s}_{v}"

    isnew = not any(p["id"] == d["id"] for p in V_["players"])
    c = st.columns([3, 1.2, 1.4, 1])
    d["name"] = c[0].text_input("Nom", d["name"], key=k("name"), placeholder="Prénom Nom")
    d["pos"] = c[1].selectbox("Position", ["F", "D", "G"], index="FDG".index(d.get("pos", "F")),
                              format_func=lambda x: POS[x], key=k("pos"))
    b = c[2].date_input("Naissance", _d(d.get("birth")), min_value=date(1970, 1, 1), format="YYYY-MM-DD",
                        key=k("birth"))
    d["birth"] = b.isoformat() if b else ""
    ppm = c[3].number_input("Pts/match", value=d.get("ppm"), min_value=0.0, step=0.01, key=k("ppm"),
                            disabled=d["pos"] == "G")
    d["ppm"] = None if d["pos"] == "G" else ppm
    d["notes"] = st.text_input("Notes", d.get("notes", ""), key=k("notes"),
                               placeholder="ex. créé pour la 1re fois, acquis par échange…")

    st.markdown(f"##### Contrat — {amt_lbl}, en millions $")
    seas = list(range(cur_, cur_ + T_["nSeasons"] + 2))
    for i in range(0, len(seas), 5):
        cols = st.columns(5)
        for y, col in zip(seas[i:i + 5], cols):
            cc = d["contract"].get(str(y)) or {}
            with col.container(border=True):
                val = st.number_input(lab(y), value=(cc["a"] / 1e6 if cc.get("a") else None), min_value=0.0,
                                      step=0.05, format="%.3f", key=k(f"a{y}"), placeholder="—")
                rr = st.checkbox("🟧 re-sign.", value=bool(cc.get("r")), key=k(f"r{y}"))
            if val:
                d["contract"][str(y)] = {"a": int(round(val * 1e6)), "r": rr}
            else:
                d["contract"].pop(str(y), None)

    fut = [y for y in years(d) if y >= cur_]
    a = age_season(d, cur_)
    st.caption(f"Âge au 1er oct. {cur_} : **{a if a is not None else '—'}** · Années restantes : **{len(fut)}** · "
               f"Fin : **{lab(fut[-1]) if fut else '—'}** · Total restant : "
               f"**{fmt(sum(d['contract'][str(y)]['a'] for y in fut)) if fut else '—'}**")

    def redo():
        ss.fdv += 1
        st.rerun(scope="fragment")

    q = st.columns(3)
    if q[0].button("➕ Prolonger d'un an", width="stretch", help="Ajoute une saison au même montant"):
        ly = last_year(d)
        if ly is not None:
            d["contract"][str(ly + 1)] = dict(d["contract"][str(ly)])
            redo()
    if q[1].button("➖ Retirer la dernière année", width="stretch"):
        ly = last_year(d)
        if ly is not None and ly >= cur_:
            d["contract"].pop(str(ly))
            redo()
    if q[2].button("🧹 Vider les saisons futures", width="stretch"):
        for y in list(d["contract"]):
            if int(y) >= cur_:
                d["contract"].pop(y)
        redo()

    with st.expander("✍️ Nouveau contrat rapide"):
        n = st.columns([1.3, 1, 1.3, 1.2])
        start = n[0].selectbox("Début", seas, format_func=lab,
                               index=seas.index(last_year(d) + 1) if last_year(d) is not None and last_year(d) + 1 in seas
                               else 0, key=k("ns"))
        ny = n[1].number_input("Années", 1, 8, 3, key=k("ny"))
        na = n[2].text_input("Montant", placeholder="4,5M ou 875000", key=k("na"))
        nr = n[3].checkbox("🟧 Re-signature", key=k("nr"))
        if st.button("Appliquer ce contrat", key=k("nb")):
            amt = parse_amt(na)
            if not amt:
                st.error("Entre un montant.")
            else:
                for y in list(d["contract"]):
                    if int(y) >= start:
                        d["contract"].pop(y)
                for j in range(int(ny)):
                    d["contract"][str(start + j)] = {"a": amt, "r": nr}
                redo()

    with st.expander("📋 Importer depuis PuckPedia"):
        st.link_button(f"Ouvrir {d['name'] or 'le joueur'} sur PuckPedia ↗", pp_url(d["name"]), disabled=not d["name"])
        st.caption(f"Sur la page PuckPedia : Ctrl/Cmd + A puis Ctrl/Cmd + C, colle ici. On prend le **{amt_lbl}**.")
        txt = st.text_area("Texte copié", height=110, key=k("pp"), label_visibility="collapsed",
                           placeholder="Colle ici le texte de la page PuckPedia…")
        if st.button("Analyser", key=k("ppb")):
            ss.fd_pp = parse_puckpedia(txt, T_.get("salaryBasis", "cap"))
        res = ss.get("fd_pp")
        if res is not None:
            if not res:
                st.error("Aucun contrat reconnu — copie toute la page.")
            chk = []
            for i, r in enumerate(res):
                ks = sorted(r["seasons"])
                chk.append(st.checkbox(f"**{r['label']}** — " + " · ".join(f"{lab(y)} {fmt(r['seasons'][y])}" for y in ks),
                                       value=any(y >= cur_ for y in ks), key=k(f"ppc{i}")))
                if r.get("note"):
                    st.warning(r["note"])
            if res and st.button("Appliquer au contrat", key=k("ppa"), type="primary"):
                for r, on in zip(res, chk):
                    if on:
                        for y, amt in r["seasons"].items():
                            if int(y) >= cur_:
                                old = d["contract"].get(str(y))
                                d["contract"][str(y)] = {"a": int(amt), "r": bool(old and old.get("r"))}
                ss.fd_pp = None
                redo()

    st.divider()
    f = st.columns([1.4, 1.6, 1])
    if f[0].button("✅ Appliquer" if not isnew else "✅ Ajouter le joueur", type="primary", width="stretch"):
        if not d["name"].strip():
            st.error("Le nom est requis.")
        else:
            d["name"] = d["name"].strip()
            snapshot()
            V_ = view()
            if isnew:
                V_["players"].append(d)
            else:
                V_["players"] = [d if p["id"] == d["id"] else p for p in V_["players"]]
            st.toast(f"{d['name']} : modifications appliquées — pense à 💾 Enregistrer.")
            close_fiche()
            st.rerun()
    if not isnew:
        with f[1]:
            conf = st.toggle("Confirmer le retrait", key=k("del"))
            if st.button("🗑 Retirer de l'alignement", disabled=not conf, width="stretch"):
                snapshot()
                V_ = view()
                V_["players"] = [p for p in V_["players"] if p["id"] != d["id"]]
                st.toast(f"{d['name']} retiré" + (" du scénario" if ss.scen else "") + " — ↶ Annuler pour revenir.")
                close_fiche()
                st.rerun()
    if f[2].button("Fermer", width="stretch"):
        close_fiche()
        st.rerun()


tabs = st.tabs(["📋 Contrats", "🔁 Re-signatures", "🧮 Édition en lot", "⚙️ Paramètres", "📜 Historique"])

# ====================================================================== 1. tableau
with tabs[0]:
    cur = T["currentSeason"]
    M = mass_by(V["players"], SZ)
    cnt = {k: sum(1 for p in V["players"] if p["pos"] == k and (p["contract"].get(str(cur)) or {}).get("a"))
           for k in POS}
    c = st.columns(5)
    c[0].metric(f"Masse {lab(cur)}", fmt(M[cur]))
    c[1].metric(f"Espace {lab(cur)}", "—" if cap_of(cur) is None else fmt(cap_of(cur) - M[cur]))
    c[2].metric(f"Engagé {lab(cur + 1)}", fmt(M.get(cur + 1, 0)))
    c[3].metric(f"Espace {lab(cur + 1)}", "—" if cap_of(cur + 1) is None else fmt(cap_of(cur + 1) - M.get(cur + 1, 0)))
    c[4].metric(f"F · D · G sous contrat", f"{cnt['F']} · {cnt['D']} · {cnt['G']}")

    f1, f2 = st.columns([3, 1])
    q = f1.text_input("Rechercher", placeholder="Nom du joueur…", label_visibility="collapsed")
    full = f2.toggle("Montants complets")
    if not V["players"]:
        st.info("Aucun joueur. Clique **＋ Nouveau joueur** (ou importe un fichier dans ⚙️ Paramètres).")

    groups = {"F": [], "D": [], "G": [], "X": []}
    for p in V["players"]:
        if q and q.lower() not in p["name"].lower():
            continue
        ly = last_year(p)
        groups["X" if ly is None or ly < cur else p["pos"]].append(p)
    for g in groups.values():
        g.sort(key=lambda p: (-max_sal(p, SZ), p["name"]))

    if can_edit and st.button("＋ Nouveau joueur", type="primary"):
        open_fiche(None)
    if can_edit:
        st.caption("👆 Clique sur un joueur pour ouvrir sa fiche (contrat, prolongation, PuckPedia, retrait).")

    GCOL = {"F": "#003087", "D": "#f47d30", "G": "#001a4a", "X": "#7a8499"}
    cols = ["Joueur", "Âge", "Pts/M"] + [lab(y) for y in SZ]
    tot = {y: 0 for y in SZ}

    def pick(key, pids):
        def _cb():
            rows = ss[key].selection.rows
            if rows and rows[0] < len(pids) and pids[rows[0]]:
                open_fiche(pids[rows[0]])
        return _cb

    for gk in ["F", "D", "G", "X"]:
        L = groups[gk]
        if gk == "X" and not L:
            continue
        title = "⚪ SANS CONTRAT / CONTRAT ÉCHU" if gk == "X" else f"{POS_ICON[gk]} {POS[gk].upper()}"
        st.markdown(f'<div style="background:{GCOL[gk]};color:#fff;font-weight:700;padding:6px 12px;'
                    f'border-radius:8px 8px 0 0;margin-top:14px">{title} ({len(L)})</div>', unsafe_allow_html=True)
        rows, css, pids = [], [], []
        sub = {y: 0 for y in SZ}
        for p in L:
            a, ly = age_season(p, cur), last_year(p)
            r = {"Joueur": f"{p['name']}  ·  {p['pos']}", "Âge": "?" if a is None else str(a),
                 "Pts/M": "G" if p["pos"] == "G" else ("—" if p.get("ppm") is None else f"{p['ppm']:.2f}".replace(".", ","))}
            s = {c_: "" for c_ in cols}
            if a is None:
                s["Âge"] = "color:#a35200;font-weight:700"
            shown = False
            for y in SZ:
                cc = p["contract"].get(str(y))
                if cc and cc.get("a"):
                    sub[y] += cc["a"]
                    r[lab(y)] = fmt(cc["a"], full)
                    if cc.get("r"):
                        s[lab(y)] = "background-color:#f47d30;color:white;font-weight:600"
                elif not shown and ly is not None and y == ly + 1:
                    shown = True
                    r[lab(y)] = "échu"
                    s[lab(y)] = "color:#8a93a8;font-style:italic"
                else:
                    r[lab(y)] = ""
            rows.append(r); css.append(s); pids.append(p["id"])
        if gk != "X":
            rows.append({"Joueur": f"Sous-total {POS[gk]}", "Âge": "", "Pts/M": "",
                         **{lab(y): fmt(sub[y], full) for y in SZ}})
            css.append({c_: "background-color:#eef2f9;font-weight:700" for c_ in cols})
            pids.append(None)
            for y in SZ:
                tot[y] += sub[y]
        if not rows:
            continue
        df = pd.DataFrame(rows, columns=cols)
        sty = df.style.apply(lambda _: pd.DataFrame(css, columns=cols), axis=None)
        key = f"tbl_{ss.team_id}_{ss.scen}_{gk}_{ss.ver}"
        cfg = {"Joueur": st.column_config.TextColumn(width="medium", pinned=True),
               "Âge": st.column_config.TextColumn(width=45), "Pts/M": st.column_config.TextColumn(width=55)}
        st.dataframe(sty, hide_index=True, width="stretch", column_config=cfg, key=key,
                     height=min(36 + 35 * len(rows), 900),
                     on_select=pick(key, pids) if can_edit else "ignore", selection_mode="single-row")

    h = ['<div class="ct-wrap" style="margin-top:14px"><table class="ct"><thead><tr><th class="l">Totaux</th>'
         + "".join(f"<th>{lab(y)}</th>" for y in SZ) + "</tr></thead><tbody>"]
    h.append('<tr class="tot"><td class="l">💰 TOTAL MASSE SALARIALE</td>'
             + "".join(f"<td>{fmt(tot[y], full)}</td>" for y in SZ) + "</tr>")
    h.append('<tr class="cap"><td class="l">📊 PLAFOND</td>'
             + "".join(f"<td>{'?' if cap_of(y) is None else fmt(cap_of(y), full)}</td>" for y in SZ) + "</tr>")
    h.append('<tr><td class="l"><b>Espace disponible</b></td>' + "".join(
        "<td>—</td>" if cap_of(y) is None else
        f'<td class="{"neg" if cap_of(y) - tot[y] < 0 else "pos"}"><b>{fmt(cap_of(y) - tot[y], full)}</b></td>'
        for y in SZ) + "</tr></tbody></table></div>")
    st.markdown("".join(h), unsafe_allow_html=True)
    st.caption(f"Montants = {AMT.lower()} · 🟧 Orange = années de re-signature · « échu » = contrat terminé · "
               f"Âge au 1er octobre {cur} (« ? » = date de naissance manquante).")


# ====================================================================== 2. re-signatures
with tabs[1]:
    cs = st.selectbox("Saison qui se termine", list(range(T["currentSeason"] - 1, T["currentSeason"] + T["nSeasons"])),
                      index=1, format_func=lambda y: f"{lab(y)} → contrats dès {lab(y + 1)}")
    exp = [p for p in V["players"] if last_year(p) == cs]
    if not exp:
        st.info(f"Aucun joueur dont le contrat se termine en {lab(cs)}.")
    else:
        rows = []
        for p in exp:
            a = age_resign(p, cs)
            rows.append({"id": p["id"], "Re-signer": False, "Joueur": p["name"], "Pos": p["pos"],
                         "Âge": a, "Hors quota": False, "Années": min(3, max_len(a)),
                         "Cap hit": float(p["contract"][str(cs)]["a"]),
                         "Max": f"{max_len(a)}" + (" (3+1 gratuite)" if a is not None and a >= 30 else ""),
                         "Dernier salaire": fmt(p["contract"][str(cs)]["a"])})
        rdf = pd.DataFrame(rows)
        rdf["Âge"] = rdf["Âge"].astype("Int64")
        rdf = rdf.rename(columns={"Cap hit": AMT})
        red = st.data_editor(
            rdf, key=f"rs_{ss.team_id}_{ss.scen}_{cs}_{ss.ver}", hide_index=True, width="stretch",
            disabled=["Joueur", "Pos", "Âge", "Max", "Dernier salaire"],
            column_config={"id": None,
                           "Années": st.column_config.NumberColumn(min_value=1, max_value=4, step=1),
                           "Hors quota": st.column_config.CheckboxColumn(
                               help="Joueur créé pour la 1re fois (ou exempté) : ne compte pas dans les "
                                    f"{R['maxResign']} re-signatures ni les {R['maxYears']} ans"),
                           AMT: st.column_config.NumberColumn(min_value=0, step=1, format="%d",
                                                              help=f"{AMT} LNH (PuckPedia)")})
        recs = [{"id": r["id"], "sign": bool(r["Re-signer"]), "created": bool(r["Hors quota"]),
                 "years": None if pd.isna(r["Années"]) else int(r["Années"]),
                 "amount": None if pd.isna(r[AMT]) else float(r[AMT])} for r in red.to_dict("records")]
        calc = resign_calc(V["players"], recs, cs, R)
        base = mass_by(V["players"], [cs + 1])[cs + 1]
        after = base + calc["add"].get(cs + 1, 0)
        m = st.columns(4)
        m[0].metric("Re-signatures comptées", f"{calc['used']} / {R['maxResign']}")
        m[1].metric("Années utilisées", f"{calc['yrs']} / {R['maxYears']}")
        m[2].metric(f"Ajout masse {lab(cs + 1)}", fmt(calc["add"].get(cs + 1, 0)))
        m[3].metric(f"Espace {lab(cs + 1)} après", "—" if cap_of(cs + 1) is None else fmt(cap_of(cs + 1) - after))
        for er in calc["errs"]:
            st.error(er)
        st.caption(f"Âge au 1er octobre {cs}. Max : ≤20 ans 3 · 21-22 ans 2 · "
                   f"23-29 ans 3 · 30+ ans 3 (+1 gratuite si 4 ans, ne compte que 3 dans les {R['maxYears']}). "
                   f"Hors quota (créé pour la 1re fois) : ne compte pas dans les {R['maxResign']} ni les {R['maxYears']} ans. "
                   + ("Montant = CAP HIT LNH actuel (PuckPedia), sinon dernier salaire LNH." if BASIS == "cap" else
                      "Montant = salaire total LNH de l'année (PuckPedia), sinon dernier salaire LNH."))
        drop = st.checkbox("Retirer de l'alignement les joueurs échus non re-signés")
        nsign = sum(r["sign"] for r in recs)
        if can_edit and st.button(f"✅ Appliquer {nsign} re-signature(s)" + (" en simulation" if ss.scen else ""),
                                  type="primary", disabled=bool(calc["errs"]) or (nsign == 0 and not drop)):
            snapshot()
            by = {p["id"]: p for p in V["players"]}
            ent = []
            for r in recs:
                p = by[r["id"]]
                if r["sign"]:
                    amt = parse_amt(r["amount"])
                    for k in range(1, r["years"] + 1):
                        p["contract"][str(cs + k)] = {"a": amt, "r": True}
                    ent.append({"name": p["name"], "years": r["years"], "amount": amt, "counted": not r["created"]})
                    if r["created"]:
                        p["notes"] = ((p.get("notes") or "") + f" · créé 1re fois (fin {lab(cs)})").strip(" ·")
            if drop:
                signed = {r["id"] for r in recs if r["sign"]}
                V["players"] = [p for p in V["players"] if p["id"] in signed or p["id"] not in {r["id"] for r in recs}]
            if ent:
                V.setdefault("history", []).append({"season": cs, "date": date.today().isoformat(), "entries": ent,
                                                    "used": calc["used"], "yearsUsed": calc["yrs"]})
            bump()
            st.toast("Re-signatures appliquées — pense à 💾 Enregistrer.")
            st.rerun()

# ====================================================================== 3. édition en lot
with tabs[2]:
    if not can_edit:
        st.info("Lecture seule — entre le mot de passe dans la barre latérale pour modifier.")
    else:
        st.markdown(f"Modifie directement les cellules, ajoute une ligne en bas, ou supprime une ligne "
                    "(coche-la à gauche puis 🗑). Montants ({AMT.lower()}) : `4500000` ou `4.5` (= millions). "
                    "Puis clique **Appliquer**.")
        plist = sorted(V["players"], key=lambda p: ("FDG".index(p["pos"]) if p["pos"] in "FDG" else 9,
                                                   -max_sal(p, SZ), p["name"]))
        rows = []
        for p in plist:
            r = {"id": p["id"], "Joueur": p["name"], "Pos": p["pos"],
                 "Naissance": _d(p.get("birth")),
                 "Pts/M": p.get("ppm"), "Notes": p.get("notes", "")}
            for y in SZ:
                cc = p["contract"].get(str(y))
                r[lab(y)] = cc["a"] if cc and cc.get("a") else None
            rows.append(r)
        cols = ["id", "Joueur", "Pos", "Naissance", "Pts/M", "Notes"] + [lab(y) for y in SZ]
        df = pd.DataFrame(rows, columns=cols)
        df["Naissance"] = pd.to_datetime(df["Naissance"]).dt.date
        for y in SZ:
            df[lab(y)] = df[lab(y)].astype("Float64")
        df["Pts/M"] = df["Pts/M"].astype("Float64")
        cfg = {"id": None,
               "Joueur": st.column_config.TextColumn(required=True, width="medium"),
               "Pos": st.column_config.SelectboxColumn(options=["F", "D", "G"], required=True, width="small"),
               "Naissance": st.column_config.DateColumn(format="YYYY-MM-DD", min_value=date(1970, 1, 1)),
               "Pts/M": st.column_config.NumberColumn(format="%.2f", step=0.01),
               "Notes": st.column_config.TextColumn(width="medium")}
        for y in SZ:
            cfg[lab(y)] = st.column_config.NumberColumn(lab(y), min_value=0, step=1, format="%d")
        ed = st.data_editor(df, key=f"ed_{ss.team_id}_{ss.scen}_{ss.ver}", num_rows="dynamic",
                            column_config=cfg, width="stretch", hide_index=True)

        st.markdown("**Années de re-signature (orange)**")
        fl = pd.DataFrame([{"id": p["id"], "Joueur": p["name"],
                            **{lab(y): bool((p["contract"].get(str(y)) or {}).get("r")) for y in SZ}} for p in plist],
                          columns=["id", "Joueur"] + [lab(y) for y in SZ])
        fcfg = {"id": None, "Joueur": st.column_config.TextColumn(disabled=True)}
        for y in SZ:
            fcfg[lab(y)] = st.column_config.CheckboxColumn(lab(y))
        fed = st.data_editor(fl, key=f"fl_{ss.team_id}_{ss.scen}_{ss.ver}", column_config=fcfg,
                             width="stretch", hide_index=True)

        if st.button("✅ Appliquer les modifications", type="primary"):
            flags = {r["id"]: r for r in fed.to_dict("records")}
            old = {p["id"]: p for p in V["players"]}
            new_players, errs = [], []
            for r in ed.to_dict("records"):
                name = (r.get("Joueur") or "").strip() if isinstance(r.get("Joueur"), str) else ""
                if not name:
                    continue
                pid = r.get("id") if isinstance(r.get("id"), str) and r.get("id") else uid()
                p = copy.deepcopy(old.get(pid, {"id": pid, "contract": {}}))
                p.update({"id": pid, "name": name, "pos": r.get("Pos") if r.get("Pos") in POS else "F",
                          "notes": r.get("Notes") if isinstance(r.get("Notes"), str) else ""})
                b = r.get("Naissance")
                p["birth"] = b.isoformat()[:10] if isinstance(b, date) and not pd.isna(b) else ""
                ppm = r.get("Pts/M")
                p["ppm"] = None if p["pos"] == "G" or ppm is None or pd.isna(ppm) else float(ppm)
                fr = flags.get(pid, {})
                for y in SZ:
                    v = r.get(lab(y))
                    amt = None if v is None or pd.isna(v) else parse_amt(float(v))
                    if amt:
                        p["contract"][str(y)] = {"a": amt, "r": bool(fr.get(lab(y), False))}
                    else:
                        p["contract"].pop(str(y), None)
                new_players.append(p)
            snapshot()
            V["players"] = new_players
            bump()
            st.toast("Modifications appliquées — pense à 💾 Enregistrer.")
            st.rerun()

# ====================================================================== 4. paramètres
with tabs[3]:
    if not can_edit:
        st.info("Lecture seule.")
    else:
        with st.form("settings"):
            s1, s2, s3 = st.columns(3)
            tname = s1.text_input("Nom de l'équipe", T["team"])
            csea = s2.number_input("Saison en cours (année de début)", 2000, 2100, T["currentSeason"],
                                   help="ex. 2026 = saison 2026-27")
            nsea = s3.number_input("Saisons affichées", 3, 12, T["nSeasons"])
            r1, r2, r3 = st.columns(3)
            mr = r1.number_input("Re-signatures max", 0, 50, R["maxResign"])
            my = r2.number_input("Années cumulées max", 0, 100, R["maxYears"])
            bs = r3.selectbox("Montant utilisé", ["cap", "total"], index=0 if BASIS == "cap" else 1,
                              format_func=lambda k: "Cap hit" if k == "cap" else "Salaire total de l'année")
            st.markdown("**Plafond salarial par saison**")
            cdf = pd.DataFrame([{"Saison": lab(y), "Plafond": float(cap_of(y)) if cap_of(y) else None}
                                for y in range(T["currentSeason"], T["currentSeason"] + T["nSeasons"])])
            cap_ed = st.data_editor(cdf, hide_index=True, disabled=["Saison"],
                                    column_config={"Plafond": st.column_config.NumberColumn(format="%d", min_value=0)})
            if st.form_submit_button("Appliquer", type="primary"):
                snapshot()
                old_cur = T["currentSeason"]
                T.update({"team": tname.strip() or T["team"], "currentSeason": int(csea), "nSeasons": int(nsea)})
                T["rules"] = {"maxResign": int(mr), "maxYears": int(my)}
                T["salaryBasis"] = bs
                for i, row in enumerate(cap_ed.to_dict("records")):
                    y = str(old_cur + i)
                    v = row["Plafond"]
                    if v is None or pd.isna(v):
                        T["caps"].pop(y, None)
                    else:
                        T["caps"][y] = int(v)
                bump()
                st.rerun()

        st.divider()
        st.markdown("**Sauvegarde / import**")
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Télécharger toutes les données (JSON)",
                           json.dumps(ss.root, ensure_ascii=False, indent=1), "contrats.json", "application/json")
        up = d2.file_uploader("Importer un JSON (remplace l'équipe affichée, ou tout si le fichier contient les 2 équipes)",
                              type="json")
        if up and st.button("Importer ce fichier"):
            try:
                o = json.loads(up.read().decode("utf-8"))
                snapshot()
                if isinstance(o.get("teams"), list):
                    ss.root = o
                elif isinstance(o.get("players"), list):
                    o["id"] = T["id"]
                    o.setdefault("scenarios", []); o.setdefault("history", [])
                    ss.root["teams"] = [o if t["id"] == T["id"] else t for t in ss.root["teams"]]
                else:
                    raise ValueError
                ss.scen = None
                bump()
                st.rerun()
            except Exception:  # noqa: BLE001
                st.error("Fichier JSON invalide.")

# ====================================================================== 5. historique
with tabs[4]:
    hist = V.get("history", [])
    if not hist:
        st.info("Aucune re-signature enregistrée pour l'instant.")
    for x in reversed(hist):
        st.markdown(f"**Fin {lab(x['season'])}** ({x.get('date', '')}) — {x['used']}/{R['maxResign']} re-signatures, "
                    f"{x['yearsUsed']}/{R['maxYears']} ans")
        for en in x["entries"]:
            st.markdown(f"- {en['name']} : {en['years']} an(s) × {fmt(en['amount'])}" + ("" if en["counted"] else " _(exempté)_"))

# ====================================================================== ouverture de la fiche
if ss.get("open_fiche") and ss.get("fd"):
    fiche()
