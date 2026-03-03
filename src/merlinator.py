# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

import logging
import sys
import os
from pathlib import Path

def get_log_path():
    """Get a writable path for the log file."""
    if getattr(sys, 'frozen', False):
        # Running as frozen executable - use user's home directory
        home = Path.home()
        log_dir = home / '.merlinclaudinator'
        log_dir.mkdir(exist_ok=True)
        return log_dir / 'merlinclaudinator.log'
    else:
        # Running in development
        return Path(__file__).parent.parent / 'merlinclaudinator.log'

# Configure logging
log_file = get_log_path()
handlers = [logging.StreamHandler(sys.stdout)]

try:
    handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
except (PermissionError, OSError) as e:
    print(f"Warning: Could not create log file at {log_file}: {e}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)
logger.info("Starting MerlinClaudinator")
logger.info("Log file: %s", log_file)
logger.info("Frozen: %s", getattr(sys, 'frozen', False))
if getattr(sys, 'frozen', False):
    logger.info("Executable path: %s", sys.executable)
    logger.info("MEIPASS: %s", getattr(sys, '_MEIPASS', 'N/A'))

from main_gui import MerlinGUI

try:
    root = MerlinGUI()
    root.mainloop()
except Exception as e:
    logger.exception("Fatal error in main loop")
    raise