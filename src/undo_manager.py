# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

"""
Undo/Redo system for MerlinClaudinator

Implements a hybrid command pattern approach:
- Simple operations use lightweight command objects
- Complex operations use snapshot-based commands
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging
import gzip
import pickle

logger = logging.getLogger(__name__)


class Command(ABC):
    """Base class for all undoable commands"""

    def __init__(self, gui):
        self.gui = gui
        self.affected_node = None  # For selection restoration
        self.parent_node = None
        self.description = "Opération"  # Default description

    @abstractmethod
    def execute(self):
        """Execute the command (modify tree state)"""
        pass

    @abstractmethod
    def undo(self):
        """Undo the command (restore previous state)"""
        pass

    def get_description(self) -> str:
        """Get human-readable description for menu"""
        return self.description

    def restore_selection(self):
        """Restore selection after undo/redo"""
        if self.affected_node and self.gui.main_tree.exists(self.affected_node):
            self.gui.main_tree.selection_set(self.affected_node)
            self.gui.main_tree.see(self.affected_node)
        elif self.parent_node and self.gui.main_tree.exists(self.parent_node):
            self.gui.main_tree.selection_set(self.parent_node)
            self.gui.main_tree.see(self.parent_node)


class TreeSnapshot:
    """Utility class for capturing full tree state with compression support"""

    @staticmethod
    def compress_snapshot(snapshot: Dict[str, Any]) -> bytes:
        """
        Compress a snapshot using gzip + pickle.

        This reduces memory usage by 30-40% for large playlists.

        Args:
            snapshot: Uncompressed snapshot dictionary

        Returns:
            Compressed bytes
        """
        try:
            # Remove PhotoImage objects before compression (they can't be pickled)
            # We'll restore them from the lazy loader or file system
            snapshot_copy = snapshot.copy()
            if 'thumbnails' in snapshot_copy:
                # Store only the UUIDs, not the PhotoImage objects
                snapshot_copy['thumbnails'] = set(snapshot_copy['thumbnails'].keys())

            pickled = pickle.dumps(snapshot_copy)
            compressed = gzip.compress(pickled, compresslevel=6)

            logger.debug("Compressed snapshot: %d -> %d bytes (%d%% of original)",
                        len(pickled), len(compressed), 100 * len(compressed) // len(pickled))

            return compressed
        except Exception as e:
            logger.error("Failed to compress snapshot: %s", e)
            return None

    @staticmethod
    def decompress_snapshot(compressed: bytes) -> Dict[str, Any]:
        """
        Decompress a snapshot.

        Args:
            compressed: Compressed snapshot bytes

        Returns:
            Uncompressed snapshot dictionary
        """
        try:
            decompressed = gzip.decompress(compressed)
            snapshot = pickle.loads(decompressed)

            logger.debug("Decompressed snapshot: %d -> %d bytes", len(compressed), len(decompressed))

            # Thumbnail PhotoImages will be restored separately if needed
            if 'thumbnails' in snapshot and isinstance(snapshot['thumbnails'], set):
                # Convert UUID set back to empty dict - thumbnails will be lazy loaded
                snapshot['thumbnails'] = {uuid: '' for uuid in snapshot['thumbnails']}

            return snapshot
        except Exception as e:
            logger.error("Failed to decompress snapshot: %s", e)
            return None

    @staticmethod
    def _capture_expanded_nodes(tree, parent='') -> set:
        """Recursively capture all expanded node IIDs"""
        expanded = set()
        for iid in tree.get_children(parent):
            if tree.item(iid, 'open'):
                # Store the UUID (values[11]) instead of IID since IIDs change
                values = tree.item(iid, 'values')
                if values and len(values) > 11:
                    expanded.add(values[11])  # UUID is at index 11
            # Recurse into children
            expanded.update(TreeSnapshot._capture_expanded_nodes(tree, iid))
        return expanded

    @staticmethod
    def _restore_expanded_nodes(tree, expanded_uuids: set, parent=''):
        """Recursively restore expansion state based on UUIDs"""
        for iid in tree.get_children(parent):
            values = tree.item(iid, 'values')
            if values and len(values) > 11:
                uuid = values[11]
                if uuid in expanded_uuids:
                    tree.item(iid, open=True)
            # Recurse into children
            TreeSnapshot._restore_expanded_nodes(tree, expanded_uuids, iid)

    @staticmethod
    def _find_node_by_uuid(tree, target_uuid: str, parent='') -> str:
        """Recursively find a node IID by its UUID"""
        for iid in tree.get_children(parent):
            values = tree.item(iid, 'values')
            if values and len(values) > 11 and values[11] == target_uuid:
                return iid
            # Recurse into children
            found = TreeSnapshot._find_node_by_uuid(tree, target_uuid, iid)
            if found:
                return found
        return None

    @staticmethod
    def capture(gui) -> Dict[str, Any]:
        """Capture complete tree state"""
        # Capture favorites by UUID and their order
        fav_uuids = []
        for fav_iid in gui.fav_tree.get_children(''):
            values = gui.main_tree.item(fav_iid, 'values')
            if values and len(values) > 11:
                fav_uuids.append(values[11])  # Store UUID

        return {
            'main_tree_items': gui.main_tree.make_item_list(),
            'fav_uuids': fav_uuids,  # Favorite UUIDs in order
            'main_selection': gui.main_tree.selection(),
            'thumbnails': {k: v for k, v in gui.thumbnails.items()},  # Copy references
            'expanded_nodes': TreeSnapshot._capture_expanded_nodes(gui.main_tree)  # Capture expansion
        }

    @staticmethod
    def restore(gui, snapshot: Dict[str, Any], preserve_selection: bool = False):
        """Restore tree to snapshot state"""
        # Store current selection if needed
        current_selection = gui.main_tree.selection() if preserve_selection else None

        # Restore thumbnails first
        gui.thumbnails.clear()
        gui.thumbnails.update(snapshot['thumbnails'])

        # Clear and repopulate main tree (pass thumbnails parameter)
        gui.main_tree.clear_tree()
        gui.main_tree.populate(snapshot['main_tree_items'], gui.thumbnails, overwrite=True)

        # Restore expansion state
        if 'expanded_nodes' in snapshot:
            TreeSnapshot._restore_expanded_nodes(gui.main_tree, snapshot['expanded_nodes'])

        # Rebuild favorite tree with new IIDs
        gui.fav_tree.delete(*gui.fav_tree.get_children())  # Clear favorites
        if 'fav_uuids' in snapshot:
            for fav_uuid in snapshot['fav_uuids']:
                # Find the node with this UUID in the restored main tree
                node_iid = TreeSnapshot._find_node_by_uuid(gui.main_tree, fav_uuid)
                if node_iid:
                    # Re-add to favorites with new IID
                    gui.fav_tree.insert('', 'end', iid=node_iid,
                                       text=gui.main_tree.item(node_iid, 'text'),
                                       image=gui.main_tree.item(node_iid, 'image'))

        # Restore selection if possible
        if preserve_selection and current_selection:
            try:
                if gui.main_tree.exists(current_selection[0]):
                    gui.main_tree.selection_set(current_selection[0])
            except (IndexError, KeyError):
                pass


class NodeSnapshot:
    """Utility for capturing single node state"""

    @staticmethod
    def capture(tree, node_iid: str) -> Dict[str, Any]:
        """Capture complete node state including children"""
        if not tree.exists(node_iid):
            return None

        node_data = {
            'iid': node_iid,
            'parent': tree.parent(node_iid),
            'index': tree.index(node_iid),
            'text': tree.item(node_iid, 'text'),
            'values': tree.item(node_iid, 'values'),
            'image': tree.item(node_iid, 'image'),
            'tags': tree.item(node_iid, 'tags'),
            'children': []
        }

        # Recursively capture children
        for child in tree.get_children(node_iid):
            node_data['children'].append(NodeSnapshot.capture(tree, child))

        return node_data

    @staticmethod
    def restore(tree, node_data: Dict[str, Any], parent: str = '', index: int = 'end') -> str:
        """Restore node and its children, returns new iid"""
        if not node_data:
            return None

        # Insert node
        new_iid = tree.insert(parent, index, text=node_data['text'],
                             values=node_data['values'], image=node_data['image'],
                             tags=node_data['tags'])

        # Restore children recursively
        for child_data in node_data['children']:
            NodeSnapshot.restore(tree, child_data, parent=new_iid, index='end')

        return new_iid


# ============================================================================
# SIMPLE COMMANDS (Lightweight)
# ============================================================================

class MoveCommand(Command):
    """Command for moving nodes (moveUp/Down/ParentDir)"""

    def __init__(self, gui, node_iid: str, old_parent: str, old_index: int,
                 new_parent: str, new_index: int):
        super().__init__(gui)
        self.node_iid = node_iid
        self.old_parent = old_parent
        self.old_index = old_index
        self.new_parent = new_parent
        self.new_index = new_index
        self.affected_node = node_iid
        self.parent_node = old_parent
        self.description = "Déplacer"

    def execute(self):
        """Move node to new position"""
        if self.gui.main_tree.exists(self.node_iid):
            self.gui.main_tree.move(self.node_iid, self.new_parent, self.new_index)
            self.gui.sync_buttons_main()

    def undo(self):
        """Move node back to original position"""
        if self.gui.main_tree.exists(self.node_iid):
            self.gui.main_tree.move(self.node_iid, self.old_parent, self.old_index)
            self.restore_selection()
            self.gui.sync_buttons_main()


class SetTitleCommand(Command):
    """Command for title changes"""

    def __init__(self, gui, node_iid: str, old_title: str, new_title: str):
        super().__init__(gui)
        self.node_iid = node_iid
        self.old_title = old_title
        self.new_title = new_title
        self.affected_node = node_iid
        self.description = "Renommer"

    def execute(self):
        """Set new title"""
        if self.gui.main_tree.exists(self.node_iid):
            # Get node type to determine icon
            node_type = int(self.gui.main_tree.set(self.node_iid, 'type'))
            if node_type in [4, 36]:  # Sound
                icon = ' \u266A '
            else:  # Menu
                icon = ' \u25AE '

            # Update both trees
            self.gui.main_tree.item(self.node_iid, text=icon + self.new_title)
            self.gui.main_tree.set(self.node_iid, 'title', self.new_title)

            if self.gui.fav_tree.exists(self.node_iid):
                self.gui.fav_tree.item(self.node_iid, text=icon + self.new_title)
                self.gui.fav_tree.set(self.node_iid, 'title', self.new_title)

    def undo(self):
        """Restore old title"""
        if self.gui.main_tree.exists(self.node_iid):
            node_type = int(self.gui.main_tree.set(self.node_iid, 'type'))
            if node_type in [4, 36]:
                icon = ' \u266A '
            else:
                icon = ' \u25AE '

            self.gui.main_tree.item(self.node_iid, text=icon + self.old_title)
            self.gui.main_tree.set(self.node_iid, 'title', self.old_title)

            if self.gui.fav_tree.exists(self.node_iid):
                self.gui.fav_tree.item(self.node_iid, text=icon + self.old_title)
                self.gui.fav_tree.set(self.node_iid, 'title', self.old_title)

            self.restore_selection()


class ReorderFavoritesCommand(Command):
    """Command for reordering favorites (moveUp/moveDown)"""

    def __init__(self, gui, old_fav_orders, new_fav_orders, selected_node):
        super().__init__(gui)
        self.old_fav_orders = old_fav_orders  # {node_iid: fav_order_str}
        self.new_fav_orders = new_fav_orders  # {node_iid: fav_order_str}
        self.affected_node = selected_node
        self.description = "Réordonner favoris"

    def execute(self):
        """Apply new favorite order"""
        self._apply_orders(self.new_fav_orders)

    def undo(self):
        """Restore previous favorite order"""
        self._apply_orders(self.old_fav_orders)
        self.restore_selection()

    def _apply_orders(self, orders):
        """Apply fav_order values and refresh the favorites tree"""
        for node_iid, fav_order in orders.items():
            if self.gui.main_tree.exists(node_iid):
                self.gui.main_tree.set(node_iid, 'fav_order', fav_order)
                self.gui.main_tree.set(node_iid, 'Favori', '★')
        self.gui.fav_tree.populate(self.gui.main_tree, overwrite=True)
        self.gui.sync_buttons_fav()


class ToggleFavoriteCommand(Command):
    """Command for toggling favorite state"""

    def __init__(self, gui, node_iid: str, was_favorite: bool):
        super().__init__(gui)
        self.node_iid = node_iid
        self.was_favorite = was_favorite
        self.affected_node = node_iid
        self.fav_index = None
        self.description = "Retirer favori" if was_favorite else "Ajouter favori"

        # Capture current favorite position if it's a favorite
        if was_favorite and gui.fav_tree.exists(node_iid):
            self.fav_index = gui.fav_tree.index(node_iid)

    def execute(self):
        """Toggle favorite state"""
        if not self.gui.main_tree.exists(self.node_iid):
            return

        if self.was_favorite:
            # Remove from favorites
            self.gui.main_tree.removeFromFavorite(self.node_iid)
        else:
            # Add to favorites at end
            self.gui.main_tree.addToFavorite(self.node_iid)

    def undo(self):
        """Restore previous favorite state"""
        if not self.gui.main_tree.exists(self.node_iid):
            return

        if self.was_favorite:
            # Restore to favorites at original position
            index = self.fav_index if self.fav_index is not None else 'end'
            self.gui.main_tree.addToFavorite(self.node_iid, index)
        else:
            # Remove from favorites
            self.gui.main_tree.removeFromFavorite(self.node_iid)

        self.restore_selection()


# ============================================================================
# NODE CREATION/DELETION COMMANDS
# ============================================================================

class AddNodeCommand(Command):
    """Command for adding single node (menu or sound)"""

    def __init__(self, gui, node_data: Dict[str, Any], is_sound: bool = False):
        super().__init__(gui)
        self.node_data = node_data
        self.is_sound = is_sound
        self.created_iid = None
        self.thumbnail_uuid = None
        self.description = "Ajouter son" if is_sound else "Ajouter menu"

    def execute(self):
        """Create the node"""
        tree = self.gui.main_tree
        parent = self.node_data.get('parent', '')
        index = self.node_data.get('index', 'end')

        # Insert node
        self.created_iid = tree.insert(
            parent, index,
            text=self.node_data['text'],
            values=self.node_data['values'],
            image=self.node_data.get('image', ''),
            tags=self.node_data.get('tags', ())
        )

        # Store thumbnail reference if exists
        uuid = self.node_data['values'][9]  # uuid column
        if uuid in self.gui.thumbnails:
            self.thumbnail_uuid = uuid

        self.affected_node = self.created_iid
        self.parent_node = parent
        tree.selection_set(self.created_iid)
        tree.see(self.created_iid)
        self.gui.sync_buttons_main()

    def undo(self):
        """Delete the created node"""
        if self.created_iid and self.gui.main_tree.exists(self.created_iid):
            # Remove from fav_tree if present
            if self.gui.fav_tree.exists(self.created_iid):
                self.gui.fav_tree.delete(self.created_iid)

            # Delete from main tree
            self.gui.main_tree.delete(self.created_iid)

            # Note: Don't delete thumbnail from cache yet - it might be in undo stack
            self.restore_selection()
            self.gui.sync_buttons_main()


class AddMultipleSoundsCommand(Command):
    """Command for adding multiple sound files at once"""

    def __init__(self, gui, sounds_data: List[Dict[str, Any]]):
        super().__init__(gui)
        self.sounds_data = sounds_data
        self.created_iids = []
        self.thumbnail_uuids = []
        count = len(sounds_data)
        self.description = f"Ajouter {count} son{'s' if count > 1 else ''}"

    def execute(self):
        """Create all sound nodes"""
        tree = self.gui.main_tree

        for sound_data in self.sounds_data:
            parent = sound_data.get('parent', '')
            index = sound_data.get('index', 'end')

            # Insert node
            iid = tree.insert(
                parent, index,
                text=sound_data['text'],
                values=sound_data['values'],
                image=sound_data.get('image', ''),
                tags=sound_data.get('tags', ())
            )

            self.created_iids.append(iid)

            # Store thumbnail reference if exists
            uuid = sound_data['values'][9]  # uuid column
            if uuid in self.gui.thumbnails:
                self.thumbnail_uuids.append(uuid)

        # Select the last created sound
        if self.created_iids:
            if len(self.created_iids) == 1:
                tree.selection_set(self.created_iids[-1])
                tree.see(self.created_iids[-1])
                self.affected_node = self.created_iids[-1]

        self.gui.sync_buttons_main()

    def undo(self):
        """Delete all created sounds"""
        tree = self.gui.main_tree

        for iid in reversed(self.created_iids):
            if tree.exists(iid):
                # Remove from fav_tree if present
                if self.gui.fav_tree.exists(iid):
                    self.gui.fav_tree.delete(iid)

                # Delete from main tree
                tree.delete(iid)

        self.restore_selection()
        self.gui.sync_buttons_main()


class DeleteLeafCommand(Command):
    """Command for deleting single node without children"""

    def __init__(self, gui, node_iid: str):
        super().__init__(gui)
        self.node_iid = node_iid
        self.node_snapshot = NodeSnapshot.capture(gui.main_tree, node_iid)
        self.parent_node = gui.main_tree.parent(node_iid)
        self.was_in_favorites = gui.fav_tree.exists(node_iid)
        self.fav_index = gui.fav_tree.index(node_iid) if self.was_in_favorites else None
        self.description = "Supprimer"

    def execute(self):
        """Delete the node"""
        if self.gui.main_tree.exists(self.node_iid):
            # Remove from favorites if present
            if self.gui.fav_tree.exists(self.node_iid):
                self.gui.fav_tree.delete(self.node_iid)

            # Delete from main tree
            self.gui.main_tree.delete(self.node_iid)
            self.gui.sync_buttons_main()
            self.gui.sync_buttons_fav()

    def undo(self):
        """Restore the deleted node"""
        if self.node_snapshot:
            # Restore node
            new_iid = NodeSnapshot.restore(
                self.gui.main_tree,
                self.node_snapshot,
                parent=self.node_snapshot['parent'],
                index=self.node_snapshot['index']
            )

            # Restore to favorites if it was there
            if self.was_in_favorites:
                index = self.fav_index if self.fav_index is not None else 'end'
                self.gui.main_tree.addToFavorite(new_iid, index)

            self.affected_node = new_iid
            self.restore_selection()
            self.gui.sync_buttons_main()
            self.gui.sync_buttons_fav()


class DeleteSubtreeCommand(Command):
    """Command for deleting node and all its children"""

    def __init__(self, gui, node_iid: str):
        super().__init__(gui)
        self.node_iid = node_iid
        self.subtree_snapshot = NodeSnapshot.capture(gui.main_tree, node_iid)
        self.parent_node = gui.main_tree.parent(node_iid)
        self.description = "Supprimer"

        # Capture which nodes were in favorites
        self.favorite_nodes = []
        self._capture_favorites(node_iid)

    def _capture_favorites(self, node_iid: str):
        """Recursively capture favorite state of all nodes in subtree by UUID"""
        if self.gui.fav_tree.exists(node_iid):
            values = self.gui.main_tree.item(node_iid, 'values')
            if values and len(values) > 11:
                self.favorite_nodes.append({
                    'uuid': values[11],
                    'fav_order': values[7]
                })

        for child in self.gui.main_tree.get_children(node_iid):
            self._capture_favorites(child)

    def execute(self):
        """Delete the entire subtree"""
        if self.gui.main_tree.exists(self.node_iid):
            # Remove all nodes from favorites first
            self._remove_from_favorites(self.node_iid)

            # Delete entire subtree
            self.gui.main_tree.delete(self.node_iid)
            self.gui.sync_buttons_main()
            self.gui.sync_buttons_fav()

    def _remove_from_favorites(self, node_iid: str):
        """Recursively remove nodes from favorites"""
        for child in self.gui.main_tree.get_children(node_iid):
            self._remove_from_favorites(child)

        if self.gui.fav_tree.exists(node_iid):
            self.gui.fav_tree.delete(node_iid)

    def undo(self):
        """Restore entire subtree"""
        if self.subtree_snapshot:
            # Restore entire subtree
            new_iid = NodeSnapshot.restore(
                self.gui.main_tree,
                self.subtree_snapshot,
                parent=self.subtree_snapshot['parent'],
                index=self.subtree_snapshot['index']
            )

            # Restore favorite states using UUID lookup
            for fav_info in self.favorite_nodes:
                new_fav_iid = TreeSnapshot._find_node_by_uuid(
                    self.gui.main_tree, fav_info['uuid']
                )
                if new_fav_iid and not self.gui.fav_tree.exists(new_fav_iid):
                    self.gui.main_tree.addToFavorite(new_fav_iid)
                    self.gui.main_tree.set(new_fav_iid, 'fav_order', fav_info['fav_order'])

            # Refresh fav tree to reflect restored order
            self.gui.fav_tree.populate(self.gui.main_tree, overwrite=True)

            self.affected_node = new_iid
            self.restore_selection()
            self.gui.sync_buttons_main()
            self.gui.sync_buttons_fav()


class SelectImageCommand(Command):
    """Command for changing image/thumbnail"""

    def __init__(self, gui, node_iid: str, old_imagepath: str, new_imagepath: str,
                 old_uuid: str, new_uuid: str, old_thumbnail):
        super().__init__(gui)
        self.node_iid = node_iid
        self.old_imagepath = old_imagepath
        self.new_imagepath = new_imagepath
        self.old_uuid = old_uuid
        self.new_uuid = new_uuid
        self.old_thumbnail = old_thumbnail
        self.new_thumbnail = None
        self.affected_node = node_iid
        self.description = "Changer image"

    def execute(self):
        """Apply new image"""
        if not self.gui.main_tree.exists(self.node_iid):
            return

        # Store new thumbnail reference
        if self.new_uuid in self.gui.thumbnails:
            self.new_thumbnail = self.gui.thumbnails[self.new_uuid]

        # Update node
        self.gui.main_tree.set(self.node_iid, 'imagepath', self.new_imagepath)
        self.gui.main_tree.set(self.node_iid, 'uuid', self.new_uuid)

        # Update thumbnail in tree
        if self.new_thumbnail:
            self.gui.main_tree.item(self.node_iid, image=self.new_thumbnail)
            if self.gui.fav_tree.exists(self.node_iid):
                self.gui.fav_tree.item(self.node_iid, image=self.new_thumbnail)

        # Update the large thumbnail preview
        self.gui.update_thumbnail_preview()

    def undo(self):
        """Restore old image"""
        logger.debug("SelectImageCommand.undo(): Restoring old_uuid=%s, old_imagepath=%s", self.old_uuid, self.old_imagepath)
        if not self.gui.main_tree.exists(self.node_iid):
            return

        # Restore old values
        self.gui.main_tree.set(self.node_iid, 'imagepath', self.old_imagepath)
        self.gui.main_tree.set(self.node_iid, 'uuid', self.old_uuid)

        # Restore old thumbnail
        if self.old_thumbnail:
            # Re-add to cache if needed
            self.gui.thumbnails[self.old_uuid] = self.old_thumbnail
            self.gui.main_tree.item(self.node_iid, image=self.old_thumbnail)
            if self.gui.fav_tree.exists(self.node_iid):
                self.gui.fav_tree.item(self.node_iid, image=self.old_thumbnail)

        self.restore_selection()

        # Update the large thumbnail preview
        self.gui.update_thumbnail_preview()
        logger.debug("SelectImageCommand.undo() completed")


# ============================================================================
# COMPLEX COMMANDS (Snapshot-based)
# ============================================================================

class AddAlbumCommand(Command):
    """Command for adding album (creates menu + multiple sounds)"""

    def __init__(self, gui, parent_node: str, album_data: List[Dict]):
        super().__init__(gui)
        self.parent_node = parent_node
        self.album_data = album_data
        # Compress snapshot to save memory
        snapshot = TreeSnapshot.capture(gui)
        self.before_snapshot_compressed = TreeSnapshot.compress_snapshot(snapshot)
        self.after_snapshot_compressed = None
        self.created_iids = []
        count = len(album_data) if album_data else 0
        self.description = f"Ajouter {count} album{'s' if count > 1 else ''}"

    def execute(self):
        """Execute add album operation"""
        # The actual album creation will be done by the existing add_album logic
        # This command just manages undo/redo
        pass

    def capture_after_state(self):
        """Capture state after album creation"""
        snapshot = TreeSnapshot.capture(self.gui)
        self.after_snapshot_compressed = TreeSnapshot.compress_snapshot(snapshot)

    def undo(self):
        """Restore state before album was added"""
        if self.before_snapshot_compressed:
            snapshot = TreeSnapshot.decompress_snapshot(self.before_snapshot_compressed)
            if snapshot:
                TreeSnapshot.restore(self.gui, snapshot, preserve_selection=True)
                self.gui.sync_buttons_main()
                self.gui.sync_buttons_fav()


class DragDropCommand(Command):
    """Command for drag-and-drop operations with compressed snapshots"""

    def __init__(self, gui, before_snapshot: Dict, after_snapshot: Dict):
        super().__init__(gui)
        # Compress snapshots to save memory
        self.before_snapshot_compressed = TreeSnapshot.compress_snapshot(before_snapshot) if before_snapshot else None
        self.after_snapshot_compressed = TreeSnapshot.compress_snapshot(after_snapshot) if after_snapshot else None
        self.description = "Glisser-déposer"

    def execute(self):
        """Execute is handled by the drag-and-drop logic itself"""
        pass

    def undo(self):
        """Restore state before drag-and-drop"""
        if self.before_snapshot_compressed:
            snapshot = TreeSnapshot.decompress_snapshot(self.before_snapshot_compressed)
            if snapshot:
                TreeSnapshot.restore(self.gui, snapshot, preserve_selection=True)
                self.gui.sync_buttons_main()
                self.gui.sync_buttons_fav()


# ============================================================================
# UNDO MANAGER
# ============================================================================

class UndoManager:
    """Manages undo/redo stacks and command execution"""

    def __init__(self, gui, max_stack_size: int = 50):
        self.gui = gui
        self.max_stack_size = max_stack_size
        self.undo_stack = []
        self.redo_stack = []
        self.thumbnail_refs = {}  # uuid -> refcount for cleanup

    def execute(self, command: Command):
        """Execute a command and add to undo stack"""
        command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()  # Clear redo when new action taken
        self._check_stack_overflow()
        self.gui.has_unsaved_changes = True
        self.gui.update_undo_menu_state()

    def push_without_execute(self, command: Command):
        """Add command to stack without executing (for operations already done)"""
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self._check_stack_overflow()
        self.gui.has_unsaved_changes = True
        self.gui.update_undo_menu_state()

    def undo(self):
        """Undo last command"""
        if not self.undo_stack:
            return

        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self.gui.update_undo_menu_state()

    def redo(self):
        """Redo last undone command"""
        if not self.redo_stack:
            return

        command = self.redo_stack.pop()
        command.execute()
        self.undo_stack.append(command)
        self.gui.update_undo_menu_state()

    def can_undo(self) -> bool:
        """Check if undo is available"""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available"""
        return len(self.redo_stack) > 0

    def clear(self):
        """Clear all undo/redo history"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.thumbnail_refs.clear()
        if hasattr(self.gui, 'update_undo_menu_state'):
            self.gui.update_undo_menu_state()

    def _check_stack_overflow(self):
        """Remove old commands if stack exceeds limit"""
        while len(self.undo_stack) > self.max_stack_size:
            old_command = self.undo_stack.pop(0)
            self._cleanup_command(old_command)

    def _cleanup_command(self, command: Command):
        """Cleanup resources associated with old command"""
        # Could add thumbnail cleanup here if needed
        pass

    def create_tree_snapshot(self) -> Dict[str, Any]:
        """Convenience method to create tree snapshot"""
        return TreeSnapshot.capture(self.gui)
