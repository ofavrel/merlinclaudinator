# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of merlinator, and is released under the 
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

import argparse

from main_gui import MerlinGUI

def parse_args():
    parser = argparse.ArgumentParser(
        prog="merlinator",
        description="Merlinator playlist editor"
    )

    parser.add_argument(
        "--playlist",
        nargs="?",
        help="Playlist (.bin), or archive (.zip) to open"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    root = MerlinGUI(args)
    root.mainloop()