# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

"""
Image processing utilities - consolidates duplicate image handling code
"""

import tkinter as tk
from PIL import Image
from PIL.ImageTk import PhotoImage
import logging

from constants import IMAGE_SIZE, IMAGE_THUMBNAIL_SIZE
from io_utils import IsImageProgressive

logger = logging.getLogger(__name__)


def check_progressive_jpeg(stream, source_name="", gui=None):
    """
    Check if a JPEG stream is progressive and warn if so.

    Args:
        stream: File-like object to check
        source_name: Name/path for the warning message
        gui: Optional GUI reference for showing warning dialog

    Returns:
        True if the image is progressive JPEG, False otherwise
    """
    if IsImageProgressive(stream):
        if gui:
            tk.messagebox.showwarning(
                title="Problème de format",
                message=f"Le format de l'image '{source_name}' est JPEG 'progressive'. "
                        f"Ce format n'est pas pris en charge par toutes les Merlin."
            )
        logger.warning("Progressive JPEG detected: %s", source_name)
        return True
    return False


class ImageProcessor:
    """
    Centralized image processing utilities.

    Consolidates duplicate code for:
    - Resizing images
    - Creating thumbnails
    - Progressive JPEG detection
    - PhotoImage creation
    """

    @staticmethod
    def resize_for_storage(image_path, output_path, size=IMAGE_SIZE):
        """
        Resize and save an image for storage on Merlin device.

        Args:
            image_path: Path to source image
            output_path: Path to save resized image
            size: Target size tuple (width, height)

        Returns:
            True if successful, False otherwise
        """
        try:
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.LANCZOS)
                img.save(output_path, "JPEG")
            logger.debug("Resized image: %s -> %s", image_path, output_path)
            return True
        except Exception as e:
            logger.error("Failed to resize image %s: %s", image_path, e)
            return False

    @staticmethod
    def create_thumbnail_photoimage(image_path, size=IMAGE_THUMBNAIL_SIZE, check_progressive=True, gui=None):
        """
        Create a PhotoImage thumbnail from an image file.

        Args:
            image_path: Path to source image
            size: Thumbnail size (will create size x size image)
            check_progressive: Whether to check for progressive JPEG
            gui: Optional GUI reference for showing warnings

        Returns:
            PhotoImage object or empty string if failed
        """
        try:
            # Check for progressive JPEG
            if check_progressive:
                with open(image_path, "rb") as imagestream:
                    if check_progressive_jpeg(imagestream, image_path, gui):
                        return ''

            # Load and resize
            with Image.open(image_path) as image:
                image_small = image.resize((size, size), Image.LANCZOS)
                return PhotoImage(image_small)

        except Exception as e:
            logger.error("Failed to create thumbnail from %s: %s", image_path, e)
            return ''

    @staticmethod
    def create_thumbnail_from_pil_image(pil_image, size=IMAGE_THUMBNAIL_SIZE):
        """
        Create a PhotoImage thumbnail from a PIL Image object.

        Args:
            pil_image: PIL Image object
            size: Thumbnail size (will create size x size image)

        Returns:
            PhotoImage object or empty string if failed
        """
        try:
            image_small = pil_image.resize((size, size), Image.LANCZOS)
            return PhotoImage(image_small)
        except Exception as e:
            logger.error("Failed to create thumbnail from PIL image: %s", e)
            return ''

    @staticmethod
    def load_and_process_image(image_path, thumbnail_size=IMAGE_THUMBNAIL_SIZE,
                                storage_path=None, storage_size=IMAGE_SIZE,
                                check_progressive=True, gui=None):
        """
        Load an image, optionally save resized version, and create thumbnail.

        This consolidates the common pattern of:
        1. Loading an image
        2. Saving a resized version for storage
        3. Creating a thumbnail for display

        Args:
            image_path: Path to source image
            thumbnail_size: Size for display thumbnail
            storage_path: Optional path to save resized image
            storage_size: Size for stored image
            check_progressive: Whether to check for progressive JPEG
            gui: Optional GUI reference for warnings

        Returns:
            Tuple of (PhotoImage thumbnail, success_bool)
        """
        try:
            # Check for progressive JPEG
            if check_progressive:
                with open(image_path, "rb") as imagestream:
                    if check_progressive_jpeg(imagestream, image_path, gui):
                        return '', False

            with Image.open(image_path) as img:
                # Save resized version if requested
                if storage_path:
                    img_copy = img.copy()
                    img_copy.thumbnail(storage_size, Image.LANCZOS)
                    img_copy.save(storage_path, "JPEG")
                    logger.debug("Saved resized image: %s", storage_path)

                # Create thumbnail
                image_small = img.resize((thumbnail_size, thumbnail_size), Image.LANCZOS)
                thumbnail = PhotoImage(image_small)
                return thumbnail, True

        except Exception as e:
            logger.error("Failed to process image %s: %s", image_path, e)
            return '', False


class TreeHelpers:
    """
    Common tree traversal and manipulation utilities.
    """

    @staticmethod
    def get_all_items_recursive(tree, parent=''):
        """
        Recursively get all items in a tree.

        Args:
            tree: Treeview widget
            parent: Parent item ID (empty string for root)

        Yields:
            Item IDs
        """
        for item_id in tree.get_children(parent):
            yield item_id
            yield from TreeHelpers.get_all_items_recursive(tree, item_id)

    @staticmethod
    def find_item_by_uuid(tree, uuid, parent=''):
        """
        Find tree item by UUID.

        Args:
            tree: Treeview widget
            uuid: UUID to search for
            parent: Parent item ID to start search from

        Returns:
            Item ID or None if not found
        """
        for item_id in tree.get_children(parent):
            try:
                item_uuid = tree.set(item_id, 'uuid')
                if item_uuid == uuid:
                    return item_id

                # Search children recursively
                found = TreeHelpers.find_item_by_uuid(tree, uuid, item_id)
                if found:
                    return found
            except tk.TclError:
                continue

        return None

    @staticmethod
    def update_item_image_by_uuid(tree, uuid, image):
        """
        Update tree item image by UUID.

        Args:
            tree: Treeview widget
            uuid: UUID of item to update
            image: PhotoImage to set

        Returns:
            True if item was found and updated
        """
        item_id = TreeHelpers.find_item_by_uuid(tree, uuid)
        if item_id:
            tree.item(item_id, image=image)
            return True
        return False

    @staticmethod
    def collect_visible_items(tree, parent='', check_expanded=True):
        """
        Collect all visible items in tree.

        Args:
            tree: Treeview widget
            parent: Parent item ID
            check_expanded: Only include children if parent is expanded

        Returns:
            List of item IDs
        """
        visible = []

        for item_id in tree.get_children(parent):
            visible.append(item_id)

            # If item is expanded, include children
            if not check_expanded or tree.item(item_id, 'open'):
                visible.extend(TreeHelpers.collect_visible_items(tree, item_id, check_expanded))

        return visible
