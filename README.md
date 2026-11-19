# 🏒 Contrats — FBP Islanders & ML Canadiens

App Streamlit pour gérer les contrats des deux équipes : tableau par saison, modification à la main,
re-signatures selon les règles de la ligue, scénarios de simulation et import PuckPedia.

- **FBP Islanders** : montants = **cap hit**
- **ML Canadiens** : montants = **salaire total** de l'année
- Âge = âge au **1er octobre** de l'année de début de la saison qui se termine
  (re-signer pour 2027-28 → âge au 1er octobre 2026)

## Mise en ligne (Streamlit Community Cloud)

1. **GitHub** : crée un dépôt `contratsMLFBP` et téléverse tout le contenu de ce dossier
   (`app.py`, `logic.py`, `storage.py`, `requirements.txt`, `data/`, `.streamlit/config.toml`, `.gitignore`).
2. **Jeton GitHub** (pour que l'app enregistre tes changements) :
   GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate.
   - Repository access : *Only select repositories* → `contratsMLFBP`
   - Permissions → Repository → **Contents : Read and write**
3. **Streamlit** : share.streamlit.io → *Create app* → dépôt `contratsMLFBP`, branche `main`, fichier `app.py`.
   Dans *Advanced settings → Secrets*, colle le contenu de `.streamlit/secrets.toml.example` rempli
   (ton jeton + un mot de passe).
4. Au premier lancement, l'app crée la branche `data` avec `data/contrats.json` (copie de départ).
   Ensuite, chaque **💾 Enregistrer** fait un commit sur cette branche : tu as donc tout l'historique
   comme sauvegarde, et l'app ne redémarre pas à chaque enregistrement.

## Utilisation

- **📋 Contrats** : vue par position, sous-totaux, masse, plafond, espace. Orange = années de re-signature.
  **Clique sur un joueur** pour ouvrir sa **fiche** :
  - montant de chaque saison (en M$) + case 🟧 re-signature;
  - **➕ Prolonger d'un an**, **➖ Retirer la dernière année**, **🧹 Vider les saisons futures**;
  - **✍️ Nouveau contrat rapide** (début, années, montant);
  - **📋 Importer depuis PuckPedia** (cap hit pour FBP, salaire total pour ML);
  - **🗑 Retirer de l'alignement**.
  **＋ Nouveau joueur** ouvre une fiche vide.
- **🔁 Re-signatures** : joueurs dont le contrat se termine; coche, choisis la durée et le montant.
  Compteurs 6 joueurs / 16 ans, durées max selon l'âge (au 1er octobre), « Hors quota » pour un joueur créé
  pour la 1re fois.
- **🧮 Édition en lot** : tableau type Excel pour changer beaucoup de choses d'un coup.
- **🧪 Scénarios** (barre latérale) : copie de l'alignement pour simuler; comparaison avec le réel;
  « Appliquer au réel » quand tu es décidé.
- **↶ Annuler** défait la dernière action; **⟳ Recharger** abandonne ce qui n'est pas enregistré.
- **⚙️ Paramètres** : saison en cours, plafonds, règles, type de montant; export/import JSON.

Rien n'est sauvegardé tant que tu ne cliques pas **💾 Enregistrer**.

## En local

```
pip install -r requirements.txt
streamlit run app.py
```
Sans secrets GitHub, l'app lit et écrit directement `data/contrats.json`.
