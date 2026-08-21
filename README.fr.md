# KeySwitch 🔑

> **Gestionnaire de clés API** — attribuez la clé d'un fournisseur à chaque application indépendamment, et basculez automatiquement par priorité lorsque le quota est épuisé.
> Développé de bout en bout avec **Pi (assistant de codage IA) + DeepSeek V4 Flash**.

🌐 Langues : [简体中文](README.md) · [English](README.en.md) · **Français** · [한국어](README.ko.md)

---

## Qu'est-ce que c'est

KeySwitch résout un vrai problème : vous avez plusieurs clés API chez plusieurs fournisseurs d'IA, utilisées par différentes applications (Pi, Codex, OpenChatCut, WorkBuddy, etc.). Quand le quota d'une clé est épuisé, vous devez normalement modifier la configuration de chaque application à la main.

KeySwitch automatise tout cela :

- **Configuration par application** du fournisseur et de la clé à utiliser ;
- **Vérifications périodiques en arrière-plan** de l'utilisation de la clé en cours, avec bascule automatique vers la prochaine clé disponible quand le seuil est atteint ;
- Quand une clé est basculée, **toutes les applications qui l'utilisent basculent en même temps** — plus besoin de modifier une par une.

Il s'agit de la réécriture Rust / Tauri 2 (qui remplace la version Python dans `L:\00-projects\apikey-switcher`).

---

## ✨ Fonctionnalités

- **Navigation à gauche + panneau à droite** (style OneWork, thème violet) : Vue d'ensemble / Matrice des clés / Fournisseurs / Réserve de clés / Applications / Paramètres
- **Mappage par application** : un tableau application × fournisseur, chaque cellule a son propre menu déroulant de clé. « Enregistrer et appliquer » n'écrit que les cellules modifiées (sauvegarde automatique avant écriture)
- **Basculement intelligent** : un minuteur d'arrière-plan vérifie l'utilisation de la clé en cours, et bascule automatiquement vers la clé disponible la plus prioritaire au seuil (100 % par défaut), en basculant toutes les applications qui l'utilisent
  - **Vérification à trois dimensions** : glissant / hebdomadaire / mensuel — **n'importe quelle** dimension atteignant le seuil marque la clé comme épuisée
  - **Repli inter-fournisseurs** : quand le même fournisseur n'a plus de clé disponible, repli vers d'autres fournisseurs dans l'ordre `prefer_providers` (par ex. opencode-go en priorité, DeepSeek en secours)
  - **Protection contre les échecs de requête** : les clés dont la requête d'utilisation a échoué (403/réseau) sont exclues des candidats à la bascule ; si la clé en cours échoue à interroger, on bascule vers une clé **interrogée avec succès lors de ce cycle** (même fournisseur d'abord, sinon inter-fournisseurs), et on ne reste en place que lorsqu'aucune cible utilisable n'existe.
- **Ordre de priorité** : réorganisez les clés de la réserve avec ↑↓ (l'ordre de la liste = la priorité)
- **Gestion en libre-service** : ajoutez/supprimez fournisseurs, clés API et applications directement dans l'interface
- **Édition des clés** : modifiez le fournisseur / l'identifiant / la valeur / la note / le lien de parrainage / la récompense ; un déplacement inter-fournisseurs synchronise automatiquement les mappages des applications
- **Masquage des identifiants** : les e-mails et identifiants similaires s'affichent sous la forme `4premiers***@domaine` hors mode édition ; la valeur complète est visible pendant l'édition
- **Visualisation de l'utilisation** : la carte Vue d'ensemble affiche trois barres de progression glissant/hebdomadaire/mensuel plus des comptes à rebours de réinitialisation par dimension (`réinitialise dans X j X h`)
- **Zone de notification (systray)** : clic gauche / menu pour ouvrir la fenêtre principale ; le menu affiche un aperçu de l'utilisation + l'état du basculement intelligent ; fermer la fenêtre la masque dans la zone de notification (ne quitte pas)
- **Détection de l'utilisation** : opencode-go `/usage` (pourcentage), DeepSeek `/user/balance` (solde)

---

## 📦 Installation

Téléchargez l'installeur de la release (Windows) :

| Format | Fichier | Remarques |
|---|---|---|
| Installeur NSIS | `KeySwitch_0.3.1_x64-setup.exe` | Double-cliquez pour installer, inclut un désinstalleur |
| Paquet MSI | `KeySwitch_0.3.1_x64_en-US.msi` | Pour le déploiement en entreprise |

Après l'installation, il reste résident dans la zone de notification.

---

## 🚀 Démarrage rapide

> Pour une première utilisation, suivez cet ordre — comptez environ 5 minutes de configuration.

1. **(Optionnel) Migrer depuis la version Python** : `python tools/migrate_config.py` importe l'ancienne configuration en une seule fois.
2. **Ajouter un fournisseur** : ouvrez la page « Fournisseurs » → renseignez le nom, `base_url` et le type d'utilisation (`percent` pour un pourcentage / `balance` pour un solde).
3. **Ajouter des clés** : ouvrez la page « Réserve de clés » → renseignez l'identifiant, la valeur de la clé, et éventuellement la note / le lien de parrainage / la récompense ; réordonnez la priorité avec ↑↓.
4. **Ajouter des applications** : ouvrez la page « Applications » → choisissez un adaptateur → renseignez les paramètres → choisissez quelle clé chaque fournisseur utilise pour cette application.
5. **Enregistrer et appliquer** : ouvrez la page « Matrice des clés » pour vérifier la matrice application × fournisseur → cliquez sur « Enregistrer et appliquer » (seules les cellules modifiées sont écrites, avec sauvegarde automatique).
6. **Activer le basculement intelligent** : ouvrez la page « Vue d'ensemble » → définissez le seuil / l'intervalle de vérification / l'ordre des fournisseurs préférés → activez.

Ensuite, le vérificateur d'arrière-plan résident dans la zone de notification prend le relais. Remarque : **l'application concernée doit être redémarrée** après un basculement pour prendre en compte la nouvelle clé (voir les pièges ci-dessous).

---

## 🔌 Adaptateurs pris en charge (8)

KeySwitch utilise des « adaptateurs » pour réécrire les clés à l'emplacement de configuration réel de chaque application :

| Adaptateur | Application / emplacement cible | Paramètres requis |
|---|---|---|
| `pi` | Outil Pi (`~/.pi/agent/auth.json`) | aucun |
| `env_var` | Variable d'environnement utilisateur Windows | `env` (nom de variable, défaut `OPENCODE_GO_API_KEY`) |
| `openchatcut` | OpenChatCut (`.env.local`) | aucun |
| `workbuddy` | WorkBuddy (`models.json`) | aucun |
| `codex` | Codex (fichier secret codex-router) | aucun |
| `file_json` | tout fichier de configuration JSON | `path` + `key_path` (chemin à points, ex. `opencode-go.key`) |
| `file_env` | tout fichier `CLÉ=VALEUR` (type .env) | `path` + `key_name` (défaut `API_KEY`) |
| `file_regex` | remplacement par regex dans un fichier | `path` + `pattern` (avec 1 groupe de capture) + `replacement` (défaut `\1{key}\2`) |

---

## 🔄 Mécanisme de basculement intelligent

- **Déclenchement** : le minuteur effectue un tick toutes les 30 s, et décide d'exécuter la vérification selon `interval_min` (5 min par défaut). Une clé en cours est considérée comme épuisée quand **n'importe laquelle** des valeurs glissante/hebdomadaire/mensuelle ≥ `trigger_percent` (100 % par défaut).
- **Cible de bascule** : au sein du même fournisseur, choisir la première clé disponible selon la priorité de la réserve (ordre de la liste) ; sinon, repli inter-fournisseurs dans l'ordre `prefer_providers`.
- **Cohérence** : quand une clé est basculée, toutes les applications dont le `mapping` la référence basculent ensemble.
- **Prévention des faux basculements** : les clés dont la requête d'utilisation a échoué (403 / erreur réseau) sont toujours exclues des candidats à la bascule (éviter de basculer vers une clé morte) ; si la clé en cours échoue à interroger, on bascule vers une clé **interrogée avec succès lors de ce cycle** (même fournisseur d'abord, sinon inter-fournisseurs comme DeepSeek), et on reste en place uniquement lorsqu'aucune cible utilisable n'existe.
- **Journalisation** : chaque vérification ajoute une ligne à `%APPDATA%\KeySwitch\auto-switch.log`, pour confirmer que le minuteur tourne.

---

## ⚙️ Configuration

- Chemin : `%APPDATA%\KeySwitch\config.toml` (écrit automatiquement par l'interface ; modifiable à la main)
- Sections clés :

```toml
[auto_switch]
enabled = true          # activer le basculement intelligent
interval_min = 5        # intervalle de vérification (minutes)
trigger_percent = 100   # seuil de déclenchement (%)
prefer_providers = ["opencode-go", "deepseek"]  # ordre de repli inter-fournisseurs (optionnel)

[providers.opencode-go]
base_url = "https://api.opencode.ai"
usage_type = "percent"  # percent | balance
```

- Champs optionnels par clé : `note`, `promo_url`, `reward`.
- Champs optionnels par application (`targets`) : `label`, `adapter`, paramètres d'adaptateur (`env`/`path`/`key_path`/`key_name`/`pattern`/`replacement`), `mapping`.

---

## 🛠 Stack technique & méthode de développement

| Couche | Technologie |
|---|---|
| Frontend | React 18 + TypeScript + Vite (`src/`) |
| Backend | Rust + Tauri 2 (`src-tauri/`) |
| Configuration | TOML (`%APPDATA%\KeySwitch\config.toml`) |

> **Développé avec** : ce projet a été développé de bout en bout avec **Pi (assistant de codage IA) + DeepSeek V4 Flash**, en appliquant une discipline d'ingénierie « premiers principes + revue contradictoire » à chaque couche.

---

## 🧪 Développement & compilation

```bash
# installer les dépendances
npm install
# développement frontend (rechargement à chaud)
npm run tauri dev
# vérification des types frontend
npx tsc --noEmit
# compilation backend + tests unitaires
cd src-tauri && cargo build && cargo test
# empaquetage (NSIS / MSI)
npx tauri build
```

Sortie des installeurs :

- `src-tauri\target\release\bundle\nsis\KeySwitch_0.3.1_x64-setup.exe`
- `src-tauri\target\release\bundle\msi\KeySwitch_0.3.1_x64_en-US.msi`

> La source de l'icône de l'application est `app-icon.svg` à la racine du dépôt (clé dorée sur fond violet). Après modification, exécutez `npx tauri icon app-icon.svg` pour régénérer toutes les icônes de plateforme.

---

## ⚠️ Pièges courants (leçons apprises)

1. **Les nouvelles clés opencode-go nécessitent l'opt-in des modèles hébergés en Chine** : certains nouveaux comptes reçoivent `403 RegionError` en appelant deepseek-v4-flash — ouvrez le lien du workspace indiqué dans l'erreur (`opencode.ai/workspace/<id>/go`) et acceptez-le dans le navigateur.
2. **Les applications doivent être redémarrées après un basculement** : KeySwitch modifie des fichiers de configuration / variables d'environnement utilisateur ; **les processus déjà en cours** (PI / DSH / applications) conservent l'ancienne clé chargée au démarrage — redémarrez-les pour prendre en compte la nouvelle clé.
3. **Nommage des arguments Tauri** : les paramètres d'`invoke` utilisent le camelCase (backend `key_id` ↔ frontend `keyId`) ; **les champs de retour des commandes sont en snake_case** (le frontend doit utiliser `weekly_reset`, pas `weeklyReset`) — les deux directions sont opposées, ne les mélangez pas.
4. **L'API d'utilisation peut diverger des limites réelles** : le pourcentage de `/usage` d'opencode-go ne garantit pas l'utilisabilité (peut renvoyer 429/403) et est bloqué par intermittence par Cloudflare ; KeySwitch exclut des candidats à la bascule les clés dont la requête a échoué lors de ce cycle (403/réseau), et quand la clé en cours échoue à interroger, il bascule vers une clé interrogée avec succès (même fournisseur d'abord, sinon inter-fournisseurs), en restant en place uniquement lorsqu'aucune cible utilisable n'existe.
5. **Applications stockant leur config dans le stockage WebView (ex. DSH)** : le fournisseur/la clé vivent dans un leveldb interne, impossible à modifier comme des fichiers — ajoutez-les depuis l'interface de l'application elle-même.

---

## 📄 Licence

[MIT](LICENSE) © 2026 DongDong

## 🔗 Dépôt

GitHub : [dongdong-agent/KeySwitch](https://github.com/dongdong-agent/KeySwitch) (branche main)
