# MerlinClaudinator

Editeur de playlist pour l'enceinte Merlin de La Chouette Radio (Bayard / Radio France).

> **Note:** Version améliorée basée sur le [fork de pol51](https://github.com/pol51/merlinator) du projet original [merlinator](https://github.com/cyril-joder/merlinator) de Cyril Joder, avec des améliorations supplémentaires ajoutées avec l'assistance de Claude AI.

---

## Fonctionnalités

- **Annuler/Rétablir complet** - Ctrl+Z / Ctrl+Y pour toutes les opérations
- **Glisser-déposer intuitif** - Retour visuel avec indicateurs de zone de dépôt
- **Interface moderne** - Nouvelles icônes, mise en page simplifiée, grande prévisualisation des vignettes
- **Clic pour favoris** - Basculer les favoris directement dans la playlist (icône étoile)
- **Lecteur audio** - Barre de progression cliquable, bouton lecture/pause
- **Glisser-déposer d'images** - Déposez des images directement sur la prévisualisation
- **Extraction automatique des vignettes** - Pochettes d'album extraites des fichiers MP3
- **Nommage par hash** - Évite les conflits de noms et les problèmes de caractères spéciaux
- **Chargement différé** - Gestion mémoire efficace avec cache LRU
- **Import d'albums en masse** - Importez des dossiers entiers avec vignettes automatiques

---

## Installation

### Prérequis

- Python 3.10 ou supérieur
- pip (gestionnaire de paquets Python)

### Windows / macOS / Linux

1. **Installer Python** depuis [python.org](https://python.org/downloads/)

2. **Installer les dépendances :**
   ```bash
   pip install -r requirements.txt
   ```

3. **Pour la lecture audio (optionnel) :**
   ```bash
   pip install pygame
   ```

### macOS avec Homebrew

```bash
brew install python@3.11
brew install python-tk@3.11
pip3.11 install -r requirements.txt
```

---

## Utilisation

### Lancement de l'application

```bash
cd src
python merlinator.py
```

Ou double-cliquez sur `merlinator.py` dans le dossier `src`.

### Accéder à la carte SD Merlin

1. Ouvrez l'enceinte Merlin (4 vis à l'arrière)
2. Retirez la carte micro-SD du circuit imprimé
3. Insérez-la dans un lecteur de carte connecté à votre ordinateur

### Flux de travail de base

1. **Importer la playlist** : Fichier > Importer Playlist > Sélectionner `playlist.bin` de la carte SD
2. **Éditer le contenu** : Ajouter des menus, des sons, réorganiser par glisser-déposer
3. **Exporter** : Fichier > Exporter Archive pour créer un ZIP avec tous les fichiers
4. **Copier sur la carte SD** : Extraire le contenu du ZIP à la racine de la carte SD

### Raccourcis clavier

| Action | Raccourci |
|--------|-----------|
| Nouvelle session | Ctrl+N |
| Ouvrir session | Ctrl+O |
| Sauvegarder session | Ctrl+S |
| Importer playlist | Ctrl+I |
| Exporter playlist | Ctrl+E |
| Exporter archive | Ctrl+X |
| Annuler | Ctrl+Z |
| Rétablir | Ctrl+Y |
| Déplacer vers le haut | Ctrl+Haut |
| Déplacer vers le bas | Ctrl+Bas |
| Déplacer vers le parent | Ctrl+Gauche |
| Supprimer | Suppr |

---

## Glisser-déposer

MerlinClaudinator supporte le glisser-déposer intuitif avec retour visuel :

- **Dépôt sur le bord haut/bas d'un élément** : Insérer avant/après (indicateur ligne bleue)
- **Dépôt au centre d'un dossier** : Déplacer dans le dossier (surbrillance bleue)
- **Glisser vers le panneau Favoris** : Ajouter aux favoris

---

## Format des fichiers

Pour la compatibilité avec l'enceinte Merlin :

| Type | Format | Taille | Notes |
|------|--------|--------|-------|
| Audio | MP3 | - | Stéréo, 128 kbps recommandé |
| Images | JPEG | 128x128 | Non-progressif (baseline) |
| Noms de fichiers | - | Max 64 octets | Encodage UTF-8 |

MerlinClaudinator gère automatiquement :
- Extraction des pochettes d'album des fichiers MP3
- Redimensionnement des images à 128x128
- Conversion des JPEG progressifs en baseline
- Génération de noms de fichiers par hash pour éviter les conflits

---

## Sauvegarder votre travail

### Fichiers de session (.json)

Sauvegardez votre travail en cours avec Fichier > Sauvegarder Session. Cela préserve :
- Structure de la playlist
- Toutes les métadonnées
- Références aux fichiers média

### Export d'archive (.zip)

Pour transférer vers l'enceinte Merlin, utilisez Fichier > Exporter Archive. Le ZIP contient :
- `playlist.bin` - Le fichier playlist
- `*.mp3` - Tous les fichiers audio
- `*.jpg` - Toutes les vignettes

---

## Dépannage

### "No module named tkinter"

Installez tkinter pour votre version de Python :
- **Ubuntu/Debian** : `sudo apt install python3-tk`
- **Fedora** : `sudo dnf install python3-tkinter`
- **macOS** : `brew install python-tk@3.11`

### La lecture audio ne fonctionne pas

La lecture audio nécessite pygame, qui peut avoir des problèmes de compatibilité sur certains systèmes :
```bash
pip install pygame
```

Si ça ne fonctionne pas, l'application fonctionne parfaitement sans prévisualisation audio.

### Les images ne s'affichent pas sur Merlin

Assurez-vous que les images sont :
- Format JPEG (pas PNG)
- Non-progressif (JPEG baseline)
- 128x128 pixels

MerlinClaudinator gère ces conversions automatiquement pour les nouveaux fichiers.

---

## Téléchargement (Utilisateurs)

**Pas besoin d'installer Python !** Téléchargez simplement l'exécutable prêt à l'emploi :

### Windows
➡️ **[Télécharger MerlinClaudinator.exe](https://github.com/ofavrel/merlinclaudinator/releases/download/v1.0.0/MerlinClaudinator-v1.0.0-win.exe)**

Double-cliquez sur le fichier pour lancer l'application.

### macOS
➡️ **[Télécharger MerlinClaudinator.app.zip](https://github.com/ofavrel/merlinclaudinator/releases/download/v1.0.0/MerlinClaudinator-v1.0.0-macos-arm64.zip)**

1. Décompressez le fichier ZIP
2. Glissez `MerlinClaudinator.app` dans le dossier Applications
3. Au premier lancement : clic droit > Ouvrir (pour contourner Gatekeeper)

---

## Créer l'exécutable (Développeurs)

### Build en un clic

**Windows** : Double-cliquez sur `build_windows.bat`

**macOS** : Double-cliquez sur `build_macos.command`
- Si le script ne s'ouvre pas, exécutez d'abord : `chmod +x build_macos.command`

Les scripts installent automatiquement les dépendances et créent l'exécutable.

### Build manuel

#### Windows

```bash
pip install pyinstaller pygame
python build_exe.py
```

L'exécutable sera créé dans `src/dist/MerlinClaudinator.exe`.

#### macOS

```bash
pip3 install pyinstaller pygame
brew install python-tk@3.11  # si nécessaire
python3 build_exe.py
```

L'application sera créée dans `src/dist/MerlinClaudinator.app`.

---

## Documentation technique

Pour les développeurs et contributeurs, voir [docs/TECHNICAL.md](docs/TECHNICAL.md) pour :
- Vue d'ensemble de l'architecture
- Système de nommage par hash
- Implémentation du système annuler/rétablir
- Détails de l'optimisation mémoire

---

## Licence

Licence MIT - Voir le fichier [LICENSE](LICENSE).

---

## Crédits

- **Projet original** : [merlinator](https://github.com/cyril-joder/merlinator) par Cyril Joder (2022)
- **Fork amélioré** : [pol51/merlinator](https://github.com/pol51/merlinator) par pol51 (2024)
- **MerlinClaudinator** : Amélioré avec l'assistance de Claude AI (2025)

---

## Rappel important

**Faites toujours une sauvegarde du contenu de votre carte SD avant de faire des modifications !**
