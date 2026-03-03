# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

"""
Constants used throughout the MerlinClaudinator application.
Centralizes all magic numbers and configuration values for easy maintenance.
"""

import sys
from pathlib import Path


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


def get_src_path(relative_path=""):
    """Get path relative to src directory, works for dev and PyInstaller."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development
        base_path = Path(__file__).parent
    if relative_path:
        return base_path / relative_path
    return base_path


# =============================================================================
# File Format Constants
# =============================================================================

# Maximum length for filenames (Merlin device constraint)
MAX_FILENAME_LENGTH = 64

# Maximum length for item titles
MAX_TITLE_LENGTH = 66

# Image size for thumbnails stored on device
IMAGE_SIZE = (128, 128)

# Image size for thumbnail display in tree view
IMAGE_THUMBNAIL_SIZE = 40

# ZIP password for encrypted archives
ZIP_PASSWORD = b"ChouetteRadio"

# =============================================================================
# UI Constants
# =============================================================================

# Default main window size (width, height)
DEFAULT_WINDOW_SIZE = (800, 600)

# Default main window position (x, y)
DEFAULT_WINDOW_POSITION = (300, 100)

# Tree view row height in pixels
TREE_ROW_HEIGHT = 40

# =============================================================================
# Undo/Redo Constants
# =============================================================================

# Maximum number of operations in undo stack
MAX_UNDO_STACK_SIZE = 50

# =============================================================================
# File Paths
# =============================================================================

# Get the src directory path (use function for PyInstaller compatibility)
SRC_DIR = get_src_path()

# Get the project root directory
PROJECT_ROOT = get_resource_path("")

# Path to default pictures ZIP file
DEFAULT_PICS_ZIP = get_resource_path('res/defaultPics.zip')

# =============================================================================
# Audio Constants
# =============================================================================

# Audio widget update interval (milliseconds)
AUDIO_UPDATE_INTERVAL = 200

# =============================================================================
# Performance Constants
# =============================================================================

# Maximum number of thumbnails to keep in cache
MAX_THUMBNAIL_CACHE_SIZE = 100

# Lazy loading enabled by default
LAZY_LOAD_THUMBNAILS = True
