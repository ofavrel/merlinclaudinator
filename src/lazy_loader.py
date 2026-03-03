# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

"""
Lazy image loader for thumbnails - loads images on-demand to improve startup time
"""

import tkinter as tk
from PIL import Image
from PIL.ImageTk import PhotoImage
import zipfile
import os.path
import logging
from collections import OrderedDict

from constants import IMAGE_THUMBNAIL_SIZE, MAX_THUMBNAIL_CACHE_SIZE, ZIP_PASSWORD
from image_utils import check_progressive_jpeg

logger = logging.getLogger(__name__)


class LazyImageLoader:
    """
    Loads thumbnails on-demand with LRU caching.

    Instead of loading all thumbnails at startup, images are loaded only
    when they become visible in the tree view. This dramatically improves
    startup time for large playlists.
    """

    def __init__(self, gui=None, max_cache_size=MAX_THUMBNAIL_CACHE_SIZE):
        """
        Initialize the lazy loader.

        Args:
            gui: Reference to main GUI (for eviction and tree updates)
            max_cache_size: Maximum number of thumbnails to keep in memory
        """
        self.gui = gui
        self.max_cache_size = max_cache_size
        self._cache = OrderedDict()  # LRU cache: {uuid: PhotoImage}
        self._pending = set()  # UUIDs currently being loaded
        self._failed = set()  # UUIDs that failed to load

        # Placeholder for missing images
        self._placeholder = None

        # Source tracking for lazy loading
        self._item_sources = {}  # {uuid: {'type': 'file'|'zip', 'path': str}}

        logger.info("LazyImageLoader initialized with cache size %d", max_cache_size)

    def register_item(self, uuid, source_type, source_path):
        """
        Register an item for lazy loading.

        Args:
            uuid: Unique identifier for the item
            source_type: 'file' or 'zip'
            source_path: Path to the image file or ZIP archive
        """
        self._item_sources[uuid] = {
            'type': source_type,
            'path': source_path
        }

    def register_items_from_list(self, items):
        """
        Bulk register items from a playlist.

        Args:
            items: List of item dicts with 'uuid' and 'imagepath' keys
        """
        for item in items:
            uuid = item['uuid']
            imagepath = item.get('imagepath', '')

            if imagepath and os.path.exists(imagepath):
                self.register_item(uuid, 'file', imagepath)

    def register_items_from_zip(self, items, zipfile_path):
        """
        Bulk register items from a ZIP archive.

        Args:
            items: List of item dicts with 'uuid' keys
            zipfile_path: Path to the ZIP archive containing images
        """
        for item in items:
            uuid = item['uuid']
            image_filename = uuid + '.jpg'
            self.register_item(uuid, 'zip', (zipfile_path, image_filename))

    def get_thumbnail(self, uuid, gui=None):
        """
        Get thumbnail for a UUID, loading it if necessary.

        Args:
            uuid: Unique identifier for the item
            gui: Reference to GUI for showing warnings

        Returns:
            PhotoImage object or empty string if not available
        """
        # Check if already in cache
        if uuid in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(uuid)
            return self._cache[uuid]

        # Check if previously failed
        if uuid in self._failed:
            return ''

        # Check if currently loading
        if uuid in self._pending:
            return ''

        # Check if registered for loading
        if uuid not in self._item_sources:
            logger.debug("UUID %s... not registered for lazy loading", uuid[:16])
            return ''

        # Load the thumbnail
        return self._load_thumbnail(uuid, gui)

    def _load_thumbnail(self, uuid, gui=None):
        """
        Load a thumbnail from its source.

        Args:
            uuid: Unique identifier for the item
            gui: Reference to GUI for showing warnings

        Returns:
            PhotoImage object or empty string if loading failed
        """
        self._pending.add(uuid)

        try:
            source = self._item_sources[uuid]
            source_type = source['type']
            source_path = source['path']

            if source_type == 'file':
                thumbnail = self._load_from_file(uuid, source_path, gui)
            elif source_type == 'zip':
                zipfile_path, image_filename = source_path
                thumbnail = self._load_from_zip(uuid, zipfile_path, image_filename, gui)
            else:
                logger.warning("Unknown source type '%s' for UUID %s...", source_type, uuid[:16])
                thumbnail = ''

            # Add to cache
            if thumbnail:
                self._add_to_cache(uuid, thumbnail)
            else:
                self._failed.add(uuid)

            return thumbnail

        except Exception as e:
            logger.error("Failed to load thumbnail for %s...: %s", uuid[:16], e)
            self._failed.add(uuid)
            return ''
        finally:
            self._pending.discard(uuid)

    def _load_from_file(self, uuid, filepath, gui=None):
        """Load thumbnail from a file."""
        if not os.path.exists(filepath):
            return ''

        try:
            # Check for progressive JPEG
            with open(filepath, "rb") as imagestream:
                if check_progressive_jpeg(imagestream, filepath, gui):
                    return ''

            # Load and resize
            with Image.open(filepath) as image:
                image_small = image.resize(
                    (IMAGE_THUMBNAIL_SIZE, IMAGE_THUMBNAIL_SIZE),
                    Image.LANCZOS
                )
                return PhotoImage(image_small)

        except Exception as e:
            logger.error("Error loading image from file %s: %s", filepath, e)
            return ''

    def _load_from_zip(self, uuid, zipfile_path, image_filename, gui=None):
        """Load thumbnail from a ZIP archive."""
        try:
            with zipfile.ZipFile(zipfile_path, 'r') as zfile:
                zippath = zipfile.Path(zfile, at=image_filename)
                if not zippath.exists():
                    return ''

                # Check for progressive JPEG
                with zfile.open(image_filename, 'r', pwd=ZIP_PASSWORD) as imagestream:
                    if check_progressive_jpeg(imagestream, image_filename, gui):
                        return ''

                # Load and resize
                with zfile.open(image_filename, 'r', pwd=ZIP_PASSWORD) as imagefile:
                    with Image.open(imagefile) as image:
                        image_small = image.resize(
                            (IMAGE_THUMBNAIL_SIZE, IMAGE_THUMBNAIL_SIZE),
                            Image.LANCZOS
                        )
                        return PhotoImage(image_small)

        except Exception as e:
            logger.error("Error loading image from ZIP %s/%s: %s", zipfile_path, image_filename, e)
            return ''

    def _add_to_cache(self, uuid, thumbnail):
        """Add thumbnail to cache, evicting oldest if necessary."""
        # Add to cache
        self._cache[uuid] = thumbnail

        # Evict oldest if cache is too large
        if len(self._cache) > self.max_cache_size:
            # Remove oldest (first item)
            oldest_uuid = next(iter(self._cache))
            evicted = self._cache.pop(oldest_uuid)
            logger.debug("Evicted thumbnail from cache: %s... (cache size: %d)", oldest_uuid[:16], len(self._cache))

            # Also remove from GUI thumbnails dictionary and clear tree images
            if self.gui:
                self._evict_from_gui(oldest_uuid)

    def _evict_from_gui(self, uuid):
        """
        Remove thumbnail from GUI and clear tree images.

        Args:
            uuid: UUID of thumbnail to evict
        """
        try:
            # Remove from thumbnails dictionary
            if uuid in self.gui.thumbnails:
                del self.gui.thumbnails[uuid]

            # Find and clear the tree item image
            from image_utils import TreeHelpers

            # Clear in main tree
            item_id = TreeHelpers.find_item_by_uuid(self.gui.main_tree, uuid)
            if item_id:
                self.gui.main_tree.item(item_id, image='')

            # Clear in favorites tree
            if self.gui.fav_tree.exists(item_id):
                self.gui.fav_tree.item(item_id, image='')

            logger.debug("Evicted thumbnail from GUI: %s...", uuid[:16])

        except Exception as e:
            logger.error("Error evicting thumbnail from GUI: %s", e)

    def prefetch(self, uuids, gui=None):
        """
        Prefetch thumbnails for a list of UUIDs.

        Useful for loading thumbnails for visible items in the tree.

        Args:
            uuids: List of UUIDs to prefetch
            gui: Reference to GUI for showing warnings
        """
        for uuid in uuids:
            if uuid not in self._cache and uuid not in self._pending and uuid not in self._failed:
                self.get_thumbnail(uuid, gui)

    def clear_cache(self):
        """Clear the thumbnail cache."""
        self._cache.clear()
        self._pending.clear()
        self._failed.clear()
        logger.info("Thumbnail cache cleared")

    def get_stats(self):
        """Get cache statistics for debugging."""
        return {
            'cached': len(self._cache),
            'pending': len(self._pending),
            'failed': len(self._failed),
            'registered': len(self._item_sources),
            'max_size': self.max_cache_size
        }

    def log_stats(self):
        """Log current cache statistics."""
        stats = self.get_stats()
        logger.info(
            "Thumbnail cache: %d/%d cached, %d registered, %d pending, %d failed",
            stats['cached'], stats['max_size'], stats['registered'],
            stats['pending'], stats['failed']
        )
