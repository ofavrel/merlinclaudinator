#!/bin/bash
# =============================================================================
# MerlinClaudinator - macOS Build Script
# =============================================================================
# Double-cliquez sur ce fichier pour créer l'application macOS.
# L'application sera créée dans src/dist/MerlinClaudinator.app
# =============================================================================

# Change to the directory where the script is located
cd "$(dirname "$0")"

echo "============================================================"
echo "  MerlinClaudinator - Build macOS"
echo "============================================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé."
    echo ""
    echo "Installez Python via Homebrew:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "  brew install python@3.11 python-tk@3.11"
    echo ""
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✓ $PYTHON_VERSION"

# Check if tkinter is available BEFORE creating venv
if ! python3 -c "import tkinter" &> /dev/null; then
    echo ""
    echo "⚠️  tkinter n'est pas disponible."
    echo ""
    echo "Installez-le via Homebrew:"
    echo "  brew install python-tk@3.11"
    echo ""
    echo "Si vous utilisez une autre version de Python, adaptez la commande:"
    echo "  brew install python-tk@3.12"
    echo "  brew install python-tk@3.13"
    echo ""
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

echo "✓ tkinter disponible"
echo ""

# Create virtual environment if it doesn't exist
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Création de l'environnement virtuel..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ Échec de la création de l'environnement virtuel"
        read -p "Appuyez sur Entrée pour fermer..."
        exit 1
    fi
    echo "✓ Environnement virtuel créé"
else
    echo "✓ Environnement virtuel existant trouvé"
fi

# Activate virtual environment
echo "Activation de l'environnement virtuel..."
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo "❌ Échec de l'activation de l'environnement virtuel"
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

echo "✓ Environnement virtuel activé"
echo ""

# Install/upgrade dependencies in venv
echo "Installation des dépendances..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install pyinstaller pygame --quiet

if [ $? -ne 0 ]; then
    echo "❌ Échec de l'installation des dépendances"
    echo ""
    echo "Essayez manuellement:"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt pyinstaller pygame"
    echo ""
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

echo "✓ Dépendances installées"
echo ""

# Run the build
echo "Lancement du build..."
echo ""
python build_exe.py

# Check if build succeeded
if [ -d "src/dist/MerlinClaudinator.app" ]; then
    echo ""
    echo "============================================================"
    echo "✓ BUILD RÉUSSI!"
    echo "============================================================"
    echo ""
    echo "Application: src/dist/MerlinClaudinator.app"
    echo ""

    # Create ZIP for distribution
    echo "Création du ZIP pour distribution..."
    cd src/dist
    rm -f MerlinClaudinator.app.zip
    zip -r -q MerlinClaudinator.app.zip MerlinClaudinator.app
    cd ../..
    echo "✓ ZIP créé: src/dist/MerlinClaudinator.app.zip"
    echo ""

    # Open the dist folder in Finder
    open src/dist

    echo "Le dossier dist a été ouvert dans le Finder."
    echo ""
elif [ -f "src/dist/MerlinClaudinator" ]; then
    echo ""
    echo "============================================================"
    echo "✓ BUILD RÉUSSI!"
    echo "============================================================"
    echo ""
    echo "Exécutable: src/dist/MerlinClaudinator"
    echo ""
    open src/dist
else
    echo ""
    echo "============================================================"
    echo "❌ BUILD ÉCHOUÉ"
    echo "============================================================"
    echo ""
    echo "Vérifiez les erreurs ci-dessus."
    echo ""
fi

echo ""
read -p "Appuyez sur Entrée pour fermer..."
