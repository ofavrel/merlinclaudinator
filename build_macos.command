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
    echo "  brew install python@3.11"
    echo ""
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✓ $PYTHON_VERSION"

# Check if pip is available
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ pip n'est pas installé."
    echo "Installez pip: python3 -m ensurepip --upgrade"
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

echo "✓ pip disponible"
echo ""

# Install/upgrade dependencies
echo "Installation des dépendances..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet
python3 -m pip install pyinstaller pygame --quiet

# Check if tkinter is available
if ! python3 -c "import tkinter" &> /dev/null; then
    echo ""
    echo "⚠️  tkinter n'est pas disponible."
    echo ""
    echo "Installez-le via Homebrew:"
    echo "  brew install python-tk@3.11"
    echo ""
    read -p "Appuyez sur Entrée pour fermer..."
    exit 1
fi

echo "✓ Dépendances installées"
echo ""

# Run the build
echo "Lancement du build..."
echo ""
python3 build_exe.py

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
