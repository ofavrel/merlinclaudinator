#!/usr/bin/env python3
"""
Build script for creating MerlinClaudinator executable.

Usage:
    python build_exe.py           # Build for current platform
    python build_exe.py --onedir  # Build as directory (faster startup on macOS)

Requirements:
    pip install pyinstaller

This will create a standalone executable in the 'dist' folder.
- Windows: MerlinClaudinator.exe
- macOS: MerlinClaudinator.app (application bundle)
- Linux: MerlinClaudinator
"""

import subprocess
import sys
import os
import platform
from pathlib import Path

def find_tkdnd_path():
    """Find the tkdnd library path for tkinterdnd2."""
    try:
        import tkinterdnd2
        tkdnd_path = Path(tkinterdnd2.__file__).parent / 'tkdnd'
        if tkdnd_path.exists():
            return str(tkdnd_path)
    except ImportError:
        pass
    return None

def main():
    # Get the project root directory
    project_root = Path(__file__).parent
    src_dir = project_root / 'src'

    # Detect platform
    is_macos = platform.system() == 'Darwin'
    is_windows = platform.system() == 'Windows'
    is_linux = platform.system() == 'Linux'

    # Check for --onedir flag (useful for macOS)
    use_onedir = '--onedir' in sys.argv

    print(f"Platform: {platform.system()}")
    print(f"Build mode: {'onedir' if use_onedir else 'onefile'}")

    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])

    # Change to src directory
    os.chdir(src_dir)

    # Base PyInstaller command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=MerlinClaudinator',
        '--windowed',                   # No console window (GUI app)
        '--noconfirm',                  # Overwrite without asking

        # Add data files
        f'--add-data=icons{os.pathsep}icons',           # Icons folder
        f'--add-data=../res{os.pathsep}res',            # Resources folder

        # Hidden imports that PyInstaller might miss
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
        '--hidden-import=PIL.ImageEnhance',
        '--hidden-import=mutagen',
        '--hidden-import=mutagen.mp3',
        '--hidden-import=mutagen.id3',

        # Collect all of tkinterdnd2
        '--collect-all=tkinterdnd2',

        # Exclude unnecessary modules to reduce size
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        '--exclude-module=pytest',
        '--exclude-module=IPython',
        '--exclude-module=jupyter',
    ]

    # Build mode: onefile or onedir
    if use_onedir:
        cmd.append('--onedir')
    else:
        cmd.append('--onefile')

    # macOS-specific options
    if is_macos:
        cmd.extend([
            '--osx-bundle-identifier=com.merlinclaudinator.app',
        ])
        # Check for .icns icon file
        icns_path = project_root / 'res' / 'MerlinClaudinator.icns'
        if icns_path.exists():
            cmd.append(f'--icon={icns_path}')
            print(f"Using macOS icon: {icns_path}")
        print("Building macOS application bundle (.app)")

    # Windows-specific options
    elif is_windows:
        # Check for .ico icon file
        ico_path = project_root / 'res' / 'MerlinClaudinator.ico'
        if ico_path.exists():
            cmd.append(f'--icon={ico_path}')
            print(f"Using Windows icon: {ico_path}")

    # Try to add tkdnd path if found
    tkdnd_path = find_tkdnd_path()
    if tkdnd_path:
        cmd.append(f'--add-data={tkdnd_path}{os.pathsep}tkinterdnd2/tkdnd')
        print(f"Found tkdnd at: {tkdnd_path}")
    else:
        print("WARNING: tkdnd not found - drag-and-drop from file explorer may not work")

    # Try to include pygame if available
    try:
        import pygame
        cmd.extend([
            '--hidden-import=pygame',
            '--collect-all=pygame',
        ])
        print("pygame found - audio support will be included")
    except ImportError:
        print("pygame not found - audio support will be disabled")

    # Add entry point
    cmd.append('merlinator.py')

    print()
    print("Building MerlinClaudinator executable...")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        subprocess.check_call(cmd)

        # Determine output path based on platform and build mode
        if is_macos:
            if use_onedir:
                exe_path = src_dir / 'dist' / 'MerlinClaudinator.app'
            else:
                exe_path = src_dir / 'dist' / 'MerlinClaudinator.app'
                if not exe_path.exists():
                    exe_path = src_dir / 'dist' / 'MerlinClaudinator'
        elif is_windows:
            exe_path = src_dir / 'dist' / 'MerlinClaudinator.exe'
        else:
            exe_path = src_dir / 'dist' / 'MerlinClaudinator'

        print()
        print("=" * 60)
        print("Build complete!")
        print(f"Executable location: {exe_path}")
        print()
        if is_macos:
            print("To install: drag MerlinClaudinator.app to /Applications")
            print("To run: double-click MerlinClaudinator.app")
            print()
            print("Note: On first run, you may need to right-click > Open")
            print("to bypass Gatekeeper security warning.")
        print()
        print("Test the executable before distributing.")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        print()
        print("Common issues:")
        print("1. Missing dependencies - run: pip install -r requirements.txt")
        if is_windows:
            print("2. Antivirus blocking - temporarily disable antivirus")
        if is_macos:
            print("2. Xcode tools missing - run: xcode-select --install")
            print("3. tkinter issues - run: brew install python-tk@3.11")
        print("4. tkinterdnd2 issues - try: pip uninstall tkinterdnd2 && pip install tkinterdnd2")
        sys.exit(1)

if __name__ == '__main__':
    main()
