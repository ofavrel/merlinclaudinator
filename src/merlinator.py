# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

import logging
import sys
from pathlib import Path

# Configure logging
log_file = Path(__file__).parent.parent / 'merlinclaudinator.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting MerlinClaudinator")

from main_gui import MerlinGUI

try:
    root = MerlinGUI()
    root.mainloop()
except Exception as e:
    logger.exception("Fatal error in main loop")
    raise