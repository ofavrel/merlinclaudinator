# Journal des modifications

Toutes les modifications notables de MerlinClaudinator sont documentées dans ce fichier.

---

## [3.0.0] - Mars 2025 - MerlinClaudinator

Version améliorée avec l'assistance de Claude AI, basée sur le fork de pol51.

### Ajouts

#### Système Annuler/Rétablir
- Support complet annuler/rétablir pour toutes les opérations (Ctrl+Z / Ctrl+Y)
- Menu Édition avec descriptions dynamiques des opérations
- Support des opérations complexes : glisser-déposer, import d'albums, suppressions en masse
- Historique de 50 opérations (configurable)
- Pattern de commande hybride : léger pour les opérations simples, snapshots pour les complexes

#### Améliorations du glisser-déposer
- Retour visuel avec indicateurs de zone de dépôt
- Indicateur ligne bleue pour insérer avant/après (haut/bas 25% de l'élément)
- Surbrillance bleue pour déposer dans un dossier (centre 50% de l'élément)
- Support de la réorganisation des dossiers au même niveau
- Gestion correcte de l'existence des éléments pendant les opérations de glissement

#### Améliorations UI/UX
- **Nouvelles icônes** : Jeu d'icônes moderne et frais pour tous les boutons
- **Interface simplifiée** : Mise en page plus claire et intuitive
- **Grande prévisualisation** : Vignette de l'élément sélectionné affichée en grand format
- **Glisser-déposer d'images** : Déposez de nouvelles images directement sur la prévisualisation
- **Barre de progression audio** : Barre de progression cliquable pour la lecture audio
- **Bouton lecture/pause** : Un seul bouton bascule entre lecture et pause
- **Clic pour favoris** : Cliquez directement sur l'icône étoile dans la playlist pour basculer les favoris (pas besoin de bouton dédié)
- **Retour au survol** : L'icône étoile apparaît au survol pour les éléments non favoris

#### Optimisation mémoire
- Chargement différé des vignettes (chargées à la demande quand visibles)
- Cache LRU avec taille configurable (défaut : 100 vignettes)
- Snapshots d'annulation compressés
- ~30-40% de réduction de l'utilisation mémoire pour les grandes playlists

#### Qualité du code
- Remplacement de tous les imports génériques par des imports explicites
- Organisation des icônes dans un dossier dédié `src/icons/`
- Structure de documentation consolidée
- Documentation technique complète ajoutée

### Corrections

- Vérification de l'existence des éléments lors du glisser-déposer (évite TclError)
- Rafraîchissement des vignettes après les opérations de glisser-déposer
- Expansion des dossiers après y avoir déplacé des éléments

---

## [2.0.0] - Octobre 2024 - Fork pol51

Fork amélioré par [pol51](https://github.com/pol51/merlinator) avec des améliorations majeures de productivité.

### Ajouts

#### Nommage des fichiers par hash SHA-256
- Fichiers nommés avec un hash SHA-256 en encodage base64 URL-safe
- Élimine les conflits de noms et les problèmes de caractères spéciaux
- Déduplication automatique des fichiers identiques
- Compatible avec la limite de 64 octets de Merlin
- Noms de fichiers originaux préservés dans l'affichage de l'interface

#### Extraction automatique des vignettes MP3
- Pochettes d'album automatiquement extraites des tags ID3v2 des MP3
- Redimensionnement automatique à 128x128 pixels
- Conversion automatique en JPEG baseline (non-progressif)
- Fallback gracieux si aucune pochette trouvée

#### Import d'albums en masse
- Bouton "Ajouter Album" pour importer des dossiers entiers
- Détection intelligente : album unique ou sous-dossiers multiples
- Extraction automatique des vignettes pour toutes les pistes
- La vignette de la première piste devient la couverture de l'album
- Retour de progression dans la console

#### Documentation améliorée
- CHANGELOG.md - Historique des versions
- HASH_NAMING.md - Explication du système de nommage par hash
- NOUVEAUTES.md - Guide des nouvelles fonctionnalités
- INSTALL.md - Guide d'installation macOS
- TEST_EXPORT.md - Guide de test de l'export

### Corrections

- Bug d'export ZIP (faute de frappe variable `file_not_found`)
- Initialisation manquante de `playlistpath`
- Gestion des chemins pour les nouvelles sessions

### Modifications

- Remplacement de `Image.ANTIALIAS` déprécié par `Image.LANCZOS`
- Ajout de la dépendance `mutagen` pour les métadonnées MP3
- Support Python 3.11 avec Homebrew sur macOS
- Gestion gracieuse quand pygame n'est pas disponible

---

## [1.0.0] - 2022 - Merlinator Original

Version originale par [Cyril Joder (djokeur)](https://github.com/cyril-joder/merlinator).

### Fonctionnalités

- Éditeur de playlist pour l'enceinte Merlin
- Import/export de playlist.bin depuis la carte SD
- Ajout de menus et de sons
- Gestion des favoris
- Réorganisation basique par glisser-déposer
- Prévisualisation audio (optionnel, nécessite pygame)
- Interface utilisateur en français

---

## Lignée du projet

```
merlinator (2022)          - Cyril Joder (djokeur)
    │                        Éditeur de playlist original
    ▼
pol51/merlinator (2024)    - pol51
    │                        + Nommage par hash, vignettes auto, import en masse
    ▼
MerlinClaudinator (2025)   - Amélioré avec Claude AI
                             + Annuler/rétablir, glisser-déposer visuel, optimisation mémoire
```

---

## Licence

Licence MIT - maintenue depuis le projet original.

## Crédits

- **Auteur original** : Cyril Joder (djokeur) - [github.com/cyril-joder/merlinator](https://github.com/cyril-joder/merlinator)
- **Auteur du fork** : pol51 - [github.com/pol51/merlinator](https://github.com/pol51/merlinator)
- **MerlinClaudinator** : Amélioré avec l'assistance de Claude AI
