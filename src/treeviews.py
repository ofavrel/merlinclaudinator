# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.


import tkinter as tk
from tkinter import filedialog
from tkinter.ttk import Treeview
from PIL import Image, ImageTk
import os.path, shutil, uuid
import time
import logging

logger = logging.getLogger(__name__)

from io_utils import IsImageProgressive, generate_file_hash, extract_and_resize_mp3_thumbnail, format_item
from constants import MAX_FILENAME_LENGTH, IMAGE_THUMBNAIL_SIZE
from image_utils import ImageProcessor, TreeHelpers



class MerlinTree(Treeview):

    def __init__(self, parent, root=None):
        Treeview.__init__(self, parent, selectmode='browse', show='tree')
        if root is None:
            self.rootGUI = parent
        else:
            self.rootGUI = root

        # Track currently hovered item for favorite star display
        self._hovered_item = None

        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.rootGUI.movemouse)
        self.bind("<ButtonRelease-1>", self.rootGUI.mouserelease)
        self.bind("<Control-Up>", self.moveUp)
        self.bind("<Control-Down>", self.moveDown)
        self.bind("<Control-Left>", self.moveParentDir)
        self.bind("<KeyPress-Control_L>", self.disable_arrows)
        self.bind("<KeyRelease-Control_L>", self.enable_arrows)
        self.bind("<KeyPress-Control_R>", self.disable_arrows)
        self.bind("<KeyRelease-Control_R>", self.enable_arrows)

        self.bind('<<TreeviewSelect>>', self.rootGUI.synchronise_selection)

        self.bind('<Double-Button-1>', self.play_sound)

        # Add motion tracking for hover effect on favorite stars
        self.bind('<Motion>', self.on_motion)
        self.bind('<Leave>', self.on_leave)

    def on_motion(self, event):
        """Handle mouse motion to show/hide favorite star on hover"""
        item = self.identify_row(event.y)

        # If hovering over a different item than before
        if item != self._hovered_item:
            # Clear the previous hovered item's star (if it wasn't a favorite)
            if self._hovered_item and self.exists(self._hovered_item) and self.tag_has('sound', self._hovered_item):
                if not self.tag_has('favorite', self._hovered_item):
                    self.set(self._hovered_item, 'Favori', '')

            # Set the new hovered item's star (if it's not already a favorite)
            if item and self.exists(item) and self.tag_has('sound', item):
                if not self.tag_has('favorite', item):
                    self.set(item, 'Favori', '☆')

            self._hovered_item = item

    def on_leave(self, event):
        """Handle mouse leaving the tree - clear hover star"""
        if self._hovered_item and self.exists(self._hovered_item) and self.tag_has('sound', self._hovered_item):
            if not self.tag_has('favorite', self._hovered_item):
                self.set(self._hovered_item, 'Favori', '')
        self._hovered_item = None

    def on_click(self, event):
        """Handle clicks - detect if clicking on Favori column to toggle favorite"""
        region = self.identify_region(event.x, event.y)
        if region == 'cell':
            column = self.identify_column(event.x)
            item = self.identify_row(event.y)

            # Check if clicking on the Favori column (#1)
            if column == '#1' and item and self.tag_has('sound', item):
                # Toggle favorite on this item
                self.toggleFavorite(item)
                return 'break'  # Prevent further processing

        # Otherwise, proceed with normal click handling (drag and drop)
        self.rootGUI.mouseclick(event)

    def disable_arrows(self, *args):
        temp = self.bind_class('Treeview', '<Up>')
        if temp: 
            self.boundUp = self.bind_class('Treeview', '<Up>')
        temp = self.bind_class('Treeview', '<Down>')
        if temp:
            self.boundDown = temp
        temp = self.bind_class('Treeview', '<Left>')
        if temp:
            self.boundLeft = temp
        self.unbind_class('Treeview', '<Up>')
        self.unbind_class('Treeview', '<Down>')
        self.unbind_class('Treeview', '<Left>')
        
    def enable_arrows(self, *args):
        self.bind_class('Treeview', '<Up>', self.boundUp)
        self.bind_class('Treeview', '<Down>', self.boundDown)
        self.bind_class('Treeview', '<Left>', self.boundLeft)
        
        
    def moveUp(self, *args):
        node = self.selection()
        if node:
            from undo_manager import MoveCommand
            old_parent = self.parent(node)
            old_index = self.index(node)
            new_index = old_index - 1
            self.rootGUI.undo_manager.execute(
                MoveCommand(self.rootGUI, node, old_parent, old_index, old_parent, new_index)
            )
            
    def moveDown(self, *args):
        node = self.selection()
        if node:
            from undo_manager import MoveCommand
            old_parent = self.parent(node)
            old_index = self.index(node)
            new_index = old_index + 1
            self.rootGUI.undo_manager.execute(
                MoveCommand(self.rootGUI, node, old_parent, old_index, old_parent, new_index)
            )
            
    def moveParentDir(self, *args):
        node = self.selection()
        if node and self.parent(node) != '':
            from undo_manager import MoveCommand
            old_parent = self.parent(node)
            old_index = self.index(node)
            new_parent = self.parent(old_parent)
            self.rootGUI.undo_manager.execute(
                MoveCommand(self.rootGUI, node, old_parent, old_index, new_parent, 'end')
            )

    def get_ancestors(self, node):
        res = [node]
        parent = self.parent(node)
        while parent:
            res.append(parent)
            parent = self.parent(parent)
        return res
 
        

class MerlinMainTree(MerlinTree):


    COL = ("Favori", "imagepath", "soundpath", "id", "parent_id", "order", "nb_children", 
           "fav_order", "type", "limit_time", "add_time", 
           "uuid", "title")

    rootItem = {'id': 1, 'parent_id': 0, 'order': 0, 'nb_children': 0, 
                'fav_order': 0, 'type': 1, 'limit_time': 0, 'add_time': 0, 
                'uuid': '', 'title': 'Root', 'imagepath': '', 'soundpath': ''}
    favItem = {'id': 2, 'parent_id': 1, 'order': 0, 'nb_children': 0,
               'fav_order': 0, 'type': 10, 'limit_time': 0, 'add_time': 0, 
               'uuid': 'cd6949db-7c5f-486a-aa2b-48a80a7950d5', 'title': 'Merlin_favorite', 
               'imagepath': '../res/defaultPics.zip', 'soundpath': ''}
    recentItem = {'id': 3, 'parent_id': 1, 'order': 1, 'nb_children': 0, 
                  'fav_order': 0, 'type': 18, 'limit_time': 0, 'add_time': 0, 
                  'uuid': '8794f486-c461-4ace-a44b-85c359f84017', 'title': 'Merlin_discover', 
                  'imagepath': '../res/defaultPics.zip', 'soundpath': ''}
    defaultItems = [rootItem, favItem, recentItem]
    
    def __init__(self, parent, root=None):
        MerlinTree.__init__(self, parent, root)
        
        self.currently_selected = []
        self.iid_Merlin_favorite = None
        self.iid_Merlin_discover = None


        self["columns"] = MerlinMainTree.COL
        self.column("#0", width=300)
        self.column("Favori", width=40, minwidth=40, stretch=tk.NO, anchor='center')
        self["displaycolumns"]=["Favori"]

        self.tag_configure("directory", foreground="grey")
        
    
    def clear_tree(self):
        """Clear all items from the tree"""
        self._hovered_item = None
        for c in self.get_children():
            self.delete(c)
        if self.iid_Merlin_discover:
            self.delete(self.iid_Merlin_discover)
            self.iid_Merlin_discover = None
        if self.iid_Merlin_favorite:
            self.delete(self.iid_Merlin_favorite)
            self.iid_Merlin_favorite = None

    def populate(self, items, thumbnails, overwrite):
        if overwrite:
            # clear existing data
            self.clear_tree()

        mapiid = dict()
        mapiid[1] = ''
        offsets = dict()
        offsets[''] = len(self.get_children())

        merge = False
        for item in (item for item in items if item['parent_id']==1):
            for c in self.get_children():
                if self.item(c, 'text')[3:] == item['title'] and \
                   self.set(c, 'uuid') == item['uuid']:
                    merge = True
                    break
            if merge:
                break
        if merge:
            self.focus_force()
            question = "Les playlists ont des éléments en commun. Fusionner les deux playlist?\n(cliquer sur Non pour joindre la nouvelle playlist à la fin)"
            answer = tk.messagebox.askyesno("Fusionner?",question)
            if not answer:
                merge = False

        # adding data
        for item in items:
            # Use star character for favorites: ★ for favorite, empty string for non-favorite (shows on hover)
            favorite = '★' if item['fav_order'] else ''
            data = tuple([ favorite] + \
                [item[key] for key in MerlinMainTree.COL[1:]])
            iid = item['id']
            if item['parent_id']==1:
                parent = ''
            else:
                parent = item['parent_id']
            if item['type']==1: # root
                continue
            elif item['type'] in {10,42} and self.iid_Merlin_favorite: # favoris
                continue
            elif item['type'] in {18,50} and self.iid_Merlin_discover: # ajouts récents
                continue
            
            data = tuple([ favorite] + \
                [item[key] for key in MerlinMainTree.COL[1:]])
            parent = mapiid[item['parent_id']]
            
            if merge:
                for c in self.get_children(parent):
                    if self.item(c, 'text')[3:] == item['title'] and \
                       self.set(c, 'uuid') == item['uuid']:
                        mapiid[item['id']] = c
                        offsets[c] = len(self.get_children(c))
                        break
                if item['id'] in mapiid:
                    offsets[parent] -= 1
                    continue
            
            iid = self.insert(parent, item['order']+offsets[parent], text=item['title'], values=data, image=thumbnails[item['uuid']])
            mapiid[item['id']] = iid
            offsets[iid] = 0
            self.set(iid, 'id', iid)
            self.set(iid, 'parent_id', parent)
            
            
            if item['type']%32 in [2, 6]: # directory 
                self.item(iid, tags="directory")
                self.item(iid, text=' \u25AE ' + self.item(iid, 'text'))
            elif item['type']%32 == 10: # favoris
                self.item(iid, tags="directory")
                self.item(iid, text=' \u25AE ' + self.item(iid, 'text'))
                self.iid_Merlin_favorite = iid
                self.detach(iid)
            elif item['type']%32==18: # ajouts récents
                self.item(iid, tags="directory")
                self.item(iid, text=' \u25AE ' + self.item(iid, 'text'))
                self.iid_Merlin_discover = iid
                self.detach(iid)
            else:
                self.item(iid, text=' \u266A ' + self.item(iid, 'text'))
                if item['fav_order']>0:
                    self.item(iid, tags=("sound", "favorite"))
                else:
                    self.item(iid, tags="sound")
                
        self.update()
                
        
    def make_item_list(self):
        
        root_item = MerlinMainTree.rootItem
        children = self.get_children('')
        root_item['nb_children'] = len(children)
        items = [root_item]
        self.nb_fav = len(self.tag_has("favorite"))
        counter = 1
        for order, c in enumerate(children):
            sublist, counter = self.subtree_to_list(c, counter, order)
            items.extend(sublist)
        order = len(children)
        if self.iid_Merlin_favorite:
            item = format_item(self.set(self.iid_Merlin_favorite))
            counter += 1
            item['id'] = counter
            item['order'] = order
            order += 1
            item['parent_id'] = root_item['id']
            root_item['nb_children'] += 1
            item['nb_children'] = self.nb_fav
            items.append(item)
        if self.iid_Merlin_discover:
            item = format_item(self.set(self.iid_Merlin_discover))
            counter += 1
            item['id'] = counter
            item['order'] = order
            order += 1
            item['parent_id'] = root_item['id']
            root_item['nb_children'] += 1
            items.append(item)
        
        return items
        
        
    def subtree_to_list(self, node, counter=0, order=0, parent=1):
        item = format_item(self.set(node))
        children = self.get_children(node)
        counter += 1
        item['id'] = counter
        item['order'] = order
        item['parent_id'] = parent
        item['nb_children'] = len(children)
        item['title'] = self.item(node, "text")[3:]
        if self.tag_has('favorite', node):
            item['fav_order'] = self.nb_fav - self.rootGUI.fav_tree.index(node)
        items = [item]
        for order, c in enumerate(children):
            sublist, counter = self.subtree_to_list(c, counter, order, item['id'])
            items.extend(sublist)
        return items, counter
           
    def set_selection(self, *args):
        self.current_selection = self.selection()
      
    
    def reset_selection(self, *args):
        self.selection_set(self.current_selection)
        self.focus(self.current_selection)

    def deleteNode(self, event=None, forceNode=None):
        if forceNode:
            # Internal recursive call - direct deletion
            node = forceNode
            if self._hovered_item == node:
                self._hovered_item = None
            if (children:=self.get_children(node)):
                for child in children:
                    self.deleteNode(event, child)
            fav_tree = self.rootGUI.fav_tree
            if fav_tree.exists(node):
                fav_tree.delete(node)
            self.delete(node)
        else:
            # User-initiated deletion - use undo command
            node = self.selection()
            if (event and event.widget in [self.rootGUI, self]) or event is None:
                if not node:
                    return

                # Prepare confirmation dialog
                if self.tag_has('directory', node):
                    node_type = 'menu'
                else:
                    node_type = 'fichier'
                detail = ''
                if node_type == 'menu' and self.get_children(node):
                    detail = " et tout ce qu'il contient"
                question = f"Effacer le {node_type} '{self.item(node, 'text')[3:]}'{detail} ?"
                answer = tk.messagebox.askyesno("Confirmation", question)

                if answer:
                    # Use undo command for user-initiated deletion
                    from undo_manager import DeleteSubtreeCommand
                    self.rootGUI.undo_manager.execute(
                        DeleteSubtreeCommand(self.rootGUI, node)
                    )


    def add_menu(self):
        current_node = self.selection()
        parent = self.parent(current_node)
        index = self.index(current_node) + 1

        # Prepare node data for undo command
        node_data = {
            'parent': parent,
            'index': index,
            'text': ' \u25AE Nouveau Menu',
            'tags': ('directory',),
            'values': ['', '', '', '0', '0', '0', '0', '0', '6', '0', str(int(time.time())), str(uuid.uuid4()), 'Nouveau Menu']
        }

        from undo_manager import AddNodeCommand
        cmd = AddNodeCommand(self.rootGUI, node_data, is_sound=False)
        self.rootGUI.undo_manager.execute(cmd)

        # Focus on title entry for immediate editing
        self.rootGUI.title_entry.focus_set()

    def add_sound(self):
        current_node = self.selection()
        playlist_dirname = os.path.dirname(self.rootGUI.playlistpath) if self.rootGUI.playlistpath else os.path.expanduser('~')
        filepaths = filedialog.askopenfilename(initialdir=playlist_dirname, filetypes=[('mp3', '*.mp3')], multiple=True)
        if not filepaths:
            return

        parent = self.parent(current_node)
        base_index = self.index(current_node) + 1
        sounds_data = []

        # Prepare all sound data first
        for idx, filepath in enumerate(filepaths):
            dirname, basename = os.path.split(filepath)
            original_name = os.path.splitext(basename)[0]

            # Générer un hash unique basé sur le contenu du fichier
            file_uuid = generate_file_hash(filepath, max_length=MAX_FILENAME_LENGTH)

            # Utiliser le nom original comme titre d'affichage
            display_title = original_name

            # Tenter d'extraire automatiquement la vignette du MP3
            image_path = os.path.join(dirname, file_uuid + '.jpg')
            thumbnail_ref = ''
            if extract_and_resize_mp3_thumbnail(filepath, image_path):
                # Charger la vignette dans l'interface
                try:
                    # Use ImageProcessor utility
                    thumbnail = ImageProcessor.create_thumbnail_photoimage(image_path, IMAGE_THUMBNAIL_SIZE, check_progressive=False)
                    if thumbnail:
                        self.rootGUI.thumbnails[file_uuid] = thumbnail
                    thumbnail_ref = self.rootGUI.thumbnails[file_uuid]
                    logger.info("Vignette extraite et associée à '%s'", file_uuid)
                except Exception as e:
                    logger.error("Erreur lors du chargement de la vignette: %s", e)
                    image_path = ''
            else:
                # Pas de vignette trouvée
                self.rootGUI.thumbnails[file_uuid] = ''
                image_path = ''

            # Build sound data for command
            sound_data = {
                'parent': parent,
                'index': base_index + idx,
                'text': ' \u266A ' + display_title,
                'tags': ('sound',),
                'values': ['', image_path, filepath, '0', '0', '0', '0', '0', '4', '0', str(int(time.time())), file_uuid, display_title],
                'image': thumbnail_ref
            }
            sounds_data.append(sound_data)

        # Execute with undo support
        from undo_manager import AddMultipleSoundsCommand
        self.rootGUI.undo_manager.execute(AddMultipleSoundsCommand(self.rootGUI, sounds_data))
        self.update()

    def add_album(self):
        """
        Ajoute un ou plusieurs dossiers comme albums.
        Si un dossier contient des MP3, il devient un album.
        Si un dossier contient d'autres dossiers avec des MP3, chaque sous-dossier devient un album.
        """
        current_node = self.selection()
        playlist_dirname = os.path.dirname(self.rootGUI.playlistpath) if self.rootGUI.playlistpath else os.path.expanduser('~')
        
        # Sélectionner un dossier
        folder_path = filedialog.askdirectory(initialdir=playlist_dirname, 
                                               title="Sélectionner un dossier (ou dossier parent d'albums)")
        if not folder_path:
            return
        
        # Détecter les dossiers à traiter
        albums_to_add = self._detect_albums(folder_path)
        
        if not albums_to_add:
            tk.messagebox.showinfo("Aucun album", "Aucun dossier contenant des MP3 n'a été trouvé.")
            return
        
        # Demander confirmation si plusieurs albums
        if len(albums_to_add) > 1:
            album_names = '\n'.join([f"  • {os.path.basename(path)}" for path in albums_to_add[:10]])
            if len(albums_to_add) > 10:
                album_names += f"\n  ... et {len(albums_to_add) - 10} autres"
            
            response = tk.messagebox.askyesno(
                "Plusieurs albums détectés",
                f"{len(albums_to_add)} album(s) détecté(s) :\n\n{album_names}\n\nAjouter tous ces albums ?"
            )
            if not response:
                return
        
        # Capture state before adding albums (for undo)
        from undo_manager import AddAlbumCommand
        before_snapshot = self.rootGUI.undo_manager.create_tree_snapshot()

        # Ajouter chaque album
        total_tracks = 0
        last_album_iid = None
        for album_path in albums_to_add:
            album_iid, tracks = self._add_single_album(current_node, album_path)
            total_tracks += tracks
            if album_iid:
                last_album_iid = album_iid

        # Ouvrir le menu parent pour voir les albums ajoutés
        if current_node and self.tag_has('directory', current_node):
            self.item(current_node, open=True)

        # Sélectionner le dernier album ajouté
        if last_album_iid:
            self.focus(last_album_iid)
            self.selection_set(last_album_iid)
            self.see(last_album_iid)

        self.update()

        # Capture state after and create undo command
        after_snapshot = self.rootGUI.undo_manager.create_tree_snapshot()
        cmd = AddAlbumCommand(self.rootGUI, current_node, albums_to_add)
        cmd.before_snapshot = before_snapshot
        cmd.after_snapshot = after_snapshot
        self.rootGUI.undo_manager.push_without_execute(cmd)

        # Message de confirmation
        tk.messagebox.showinfo(
            "Albums ajoutés",
            f"{len(albums_to_add)} album(s) ajouté(s) avec {total_tracks} piste(s) au total"
        )
    
    def _detect_albums(self, folder_path):
        """
        Détecte les dossiers d'albums (contenant des MP3) dans un dossier.
        Retourne une liste de chemins vers les albums.
        """
        albums = []
        
        # Vérifier si le dossier lui-même contient des MP3
        has_mp3 = any(f.lower().endswith('.mp3') for f in os.listdir(folder_path) 
                      if os.path.isfile(os.path.join(folder_path, f)))
        
        if has_mp3:
            # Le dossier lui-même est un album
            albums.append(folder_path)
        else:
            # Chercher dans les sous-dossiers
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isdir(item_path):
                    # Vérifier si ce sous-dossier contient des MP3
                    try:
                        has_mp3_sub = any(f.lower().endswith('.mp3') for f in os.listdir(item_path)
                                         if os.path.isfile(os.path.join(item_path, f)))
                        if has_mp3_sub:
                            albums.append(item_path)
                    except PermissionError:
                        logger.warning("Accès refusé à %s", item_path)
                        continue
        
        return sorted(albums)
    
    def _add_single_album(self, current_node, folder_path):
        """
        Ajoute un seul album. Retourne le nombre de pistes ajoutées.
        """
        folder_name = os.path.basename(folder_path)
        
        # Déterminer où créer l'album
        if not current_node:
            # Rien n'est sélectionné : créer à la racine
            parent = ''
            position = 'end'
        elif self.tag_has('directory', current_node):
            # Un menu est sélectionné : créer DEDANS
            parent = current_node
            position = 'end'
        else:
            # Un son est sélectionné : créer au même niveau (comme frère)
            parent = self.parent(current_node)
            position = self.index(current_node) + 1
        
        # Créer le menu (album)
        menu_iid = self.insert(parent, position, 
                               text=' \u25AE ' + folder_name, tags="directory")
        
        # Initialiser tous les champs du menu
        menu_uuid = str(uuid.uuid4())
        self.set(menu_iid, 'type', '6')
        self.set(menu_iid, 'add_time', str(int(time.time())))
        self.set(menu_iid, 'title', folder_name)
        self.set(menu_iid, 'uuid', menu_uuid)
        self.set(menu_iid, 'fav_order', '0')
        self.set(menu_iid, 'limit_time', '0')
        self.set(menu_iid, 'id', '0')
        self.set(menu_iid, 'parent_id', '0')
        self.set(menu_iid, 'order', '0')
        self.set(menu_iid, 'nb_children', '0')
        self.set(menu_iid, 'imagepath', '')
        self.set(menu_iid, 'soundpath', '')
        self.set(menu_iid, 'Favori', '')
        
        # Lister tous les fichiers MP3 dans le dossier
        mp3_files = []
        logger.info("Scan du dossier : %s", folder_path)
        for filename in os.listdir(folder_path):
            if filename.lower().endswith('.mp3'):
                full_path = os.path.join(folder_path, filename)
                mp3_files.append(full_path)
                logger.debug("MP3 trouvé : %s", filename)
        
        # Trier par nom de fichier
        mp3_files.sort()

        logger.info("Total MP3 trouvés : %d", len(mp3_files))
        
        if not mp3_files:
            logger.warning("Aucun MP3 dans %s", folder_name)
            self.delete(menu_iid)
            return None, 0
        
        menu_image_path = None

        # Ajouter chaque MP3 comme son dans le menu
        logger.info("Ajout des MP3 dans le menu '%s'...", folder_name)
        for idx, mp3_path in enumerate(mp3_files, 1):
            basename = os.path.basename(mp3_path)
            original_name = os.path.splitext(basename)[0]

            logger.debug("[%d/%d] Traitement de '%s'...", idx, len(mp3_files), original_name)
            
            # Générer un hash unique
            file_uuid = generate_file_hash(mp3_path, max_length=MAX_FILENAME_LENGTH)
            logger.debug("Hash généré : %s...", file_uuid[:20])
            
            # Créer le son dans le menu
            sound_iid = self.insert(menu_iid, 'end', text=' \u266A ' + original_name, tags='sound')
            logger.debug("Son créé avec iid : %s", sound_iid)
            
            # Initialiser tous les champs
            self.set(sound_iid, 'type', '4')
            self.set(sound_iid, 'soundpath', mp3_path)
            self.set(sound_iid, 'add_time', str(int(time.time())))
            self.set(sound_iid, 'uuid', file_uuid)
            self.set(sound_iid, 'title', original_name)
            self.set(sound_iid, 'fav_order', '0')
            self.set(sound_iid, 'limit_time', '0')
            self.set(sound_iid, 'id', '0')
            self.set(sound_iid, 'parent_id', '0')
            self.set(sound_iid, 'order', '0')
            self.set(sound_iid, 'nb_children', '0')
            self.set(sound_iid, 'Favori', '')
            
            # Extraire la vignette
            image_path = os.path.join(folder_path, file_uuid + '.jpg')
            if extract_and_resize_mp3_thumbnail(mp3_path, image_path):
                try:
                    # Use ImageProcessor utility
                    thumbnail = ImageProcessor.create_thumbnail_photoimage(image_path, IMAGE_THUMBNAIL_SIZE, check_progressive=False)
                    if thumbnail:
                        self.rootGUI.thumbnails[file_uuid] = thumbnail
                    self.item(sound_iid, image=self.rootGUI.thumbnails[file_uuid])
                    self.set(sound_iid, 'imagepath', image_path)
                    
                    # Utiliser la première vignette trouvée pour le menu
                    if menu_image_path is None:
                        menu_image_path = image_path

                    logger.info("Vignette extraite pour '%s'", original_name)
                except Exception as e:
                    logger.error("Erreur lors du chargement de la vignette: %s", e)
                    self.rootGUI.thumbnails[file_uuid] = ''
                    self.set(sound_iid, 'imagepath', '')
            else:
                self.rootGUI.thumbnails[file_uuid] = ''
                self.set(sound_iid, 'imagepath', '')
        
        # Appliquer la première vignette au menu
        if menu_image_path:
            try:
                # Use ImageProcessor utility
                thumbnail = ImageProcessor.create_thumbnail_photoimage(menu_image_path, IMAGE_THUMBNAIL_SIZE, check_progressive=False)
                if thumbnail:
                    self.rootGUI.thumbnails[menu_uuid] = thumbnail
                    self.item(menu_iid, image=self.rootGUI.thumbnails[menu_uuid])
                    self.set(menu_iid, 'imagepath', menu_image_path)
                logger.info("Image du menu '%s' définie", folder_name)
            except Exception as e:
                logger.error("Erreur lors de la définition de l'image du menu: %s", e)
        
        # Ouvrir le menu pour voir son contenu
        self.item(menu_iid, open=True)
        self.update()

        logger.info("Album '%s' ajouté avec %d piste(s)", folder_name, len(mp3_files))
        return menu_iid, len(mp3_files)

    def select_image(self):
        current_node = self.selection()
        playlist_dirname = os.path.dirname(self.rootGUI.playlistpath) if self.rootGUI.playlistpath else os.path.expanduser('~')
        if not current_node:
            return

        # Capture old state for undo
        old_imagepath = self.set(current_node, 'imagepath')
        old_uuid = self.set(current_node, 'uuid')
        old_thumbnail = self.rootGUI.thumbnails.get(old_uuid, '')

        uuid = old_uuid
        if uuid:
            initfile = uuid+'.jpg'
        else:
            initfile = ''
        filepath = filedialog.askopenfilename(initialdir=playlist_dirname, initialfile=initfile, filetypes=[('images jpg', '*.jpg')])
        if not filepath:
            return
        with open(filepath, 'rb') as stream:
            if IsImageProgressive(stream):
                tk.messagebox.showwarning(title="Problème de format", message=f"Le format de l'image est JPEG 'progressive'. Ce format n'est pas pris en charge par toutes les Merlin.")
        dirname, basename = os.path.split(filepath)
        root, ext = os.path.splitext(basename)
        # check length
        if self.tag_has('directory', current_node):
            b = root.encode('UTF-8')
            new_filepath = filepath
            while len(b) > MAX_FILENAME_LENGTH:
                b = b[:MAX_FILENAME_LENGTH + 1]
                valid = False
                while not valid:
                    b = b[:-1]
                    try:
                        new_root = b.decode('UTF-8')
                        valid = root.startswith(new_root)
                    except UnicodeError:
                        pass
                new_basename = new_root + ext
                answer = tk.messagebox.askokcancel("Nom de fichier trop long", f"Le nom de fichier '{basename}' est trop long.\nLe copier sous un nouveau nom ?")
                if not answer:
                    return
                new_filepath = tk.filedialog.asksaveasfilename(initialdir=dirname, initialfile=new_basename, filetypes=[('jpg', '*.jpg')], multiple=False)
                if not new_filepath:
                    return
                new_dirname, new_basename = os.path.split(new_filepath)
                new_root, ext = os.path.splitext(new_basename)
                b = new_uuid.encode('UTF-8')
            if new_filepath != filepath:
                uuid = new_uuid
                filepath = new_filepath                
                shutil.copyfile(filepath, new_filepath)
            self.set(current_node, 'uuid', uuid)

        # Load new thumbnail using ImageProcessor utility
        thumbnail = ImageProcessor.create_thumbnail_photoimage(filepath, IMAGE_THUMBNAIL_SIZE, check_progressive=True, gui=self.rootGUI)
        if thumbnail:
            self.rootGUI.thumbnails[uuid] = thumbnail

        # Update tree view
        new_imagepath = filepath
        new_uuid = uuid

        # Use undo command
        from undo_manager import SelectImageCommand
        cmd = SelectImageCommand(self.rootGUI, current_node, old_imagepath, new_imagepath,
                                 old_uuid, new_uuid, old_thumbnail)
        # Command needs to just update without re-executing since we already loaded the thumbnail
        self.item(current_node, image=self.rootGUI.thumbnails[uuid])
        self.set(current_node, 'imagepath', filepath)
        self.rootGUI.undo_manager.push_without_execute(cmd)

        self.update()

        # Update the large thumbnail preview
        self.rootGUI.update_thumbnail_preview()


    def toggleFavorite(self, node=None, *args):
        # If no node provided, use selection
        if not node:
            node = self.selection()
        if node:
            from undo_manager import ToggleFavoriteCommand
            was_favorite = self.tag_has('favorite', node)
            self.rootGUI.undo_manager.execute(
                ToggleFavoriteCommand(self.rootGUI, node, was_favorite)
            )

    def addToFavorite(self, node, index='end'):
        if node and self.tag_has('sound', node) and not self.tag_has('favorite', node):
            self.item(node, tags=('sound', 'favorite'))
            self.set(node, 'Favori', '★')  # Filled star for favorites
            self.rootGUI.fav_tree.insert('', index, iid=node, \
                                         text=self.item(node, 'text'), \
                                         image=self.item(node, 'image'))
            self.rootGUI.fav_tree.selection_set(node)
            self.rootGUI.fav_tree.see(node)
            self.update()
            self.rootGUI.fav_tree.update()
            self.rootGUI.sync_buttons_fav()

    def removeFromFavorite(self, node):
        if node and self.tag_has('sound', node):
            self.item(node, tags=('sound'))
            self.set(node, 'Favori', '')  # Clear star for non-favorites (will show on hover)
            self.rootGUI.fav_tree.delete(node)
            self.update()
            self.rootGUI.fav_tree.update()
            self.rootGUI.sync_buttons_fav()
            
            
    def play_sound(self, event):
        if self.rootGUI.enable_audio:
            node = self.identify_row(event.y)
            if self.tag_has('sound', node):
                self.rootGUI.audio_widget.Play()
 

    

class MerlinFavTree(MerlinTree):

    def __init__(self, parent, root=None):
        MerlinTree.__init__(self, parent, root)


    def populate(self, main_tree, overwrite):
        if overwrite:
            # clear existing data
            for c in self.get_children():
                self.delete(c)

        # add data
        nb_children = len(self.get_children())
        fav_list = sorted([(int(main_tree.set(node,'fav_order')), node) for node in main_tree.tag_has('favorite') if not self.exists(node)], reverse=True)
        for order, fav in enumerate(fav_list):
            node = fav[1]
            self.insert('', order+nb_children, iid=node, text=main_tree.item(node, 'text'), \
                        image=main_tree.item(node, 'image'))
        self.update()

    def _reorder_favorites(self, all_favs, node):
        """Apply new fav_order values and push to undo stack.

        Args:
            all_favs: List of node IIDs in desired new order
            node: The node being moved (for selection restoration)
        """
        from undo_manager import ReorderFavoritesCommand

        # Capture old fav_order values before modification
        old_fav_orders = {
            fav_node: self.rootGUI.main_tree.set(fav_node, 'fav_order')
            for fav_node in all_favs
        }

        # Recalculate ALL fav_order values based on new positions
        # Higher index = lower fav_order (reversed, so first item has highest fav_order)
        total_favs = len(all_favs)
        for i, fav_node in enumerate(all_favs):
            new_fav_order = total_favs - i
            self.rootGUI.main_tree.set(fav_node, 'fav_order', str(new_fav_order))
            self.rootGUI.main_tree.set(fav_node, 'Favori', '★')

        # Capture new fav_order values after modification
        new_fav_orders = {
            fav_node: self.rootGUI.main_tree.set(fav_node, 'fav_order')
            for fav_node in all_favs
        }

        # Push to undo stack
        self.rootGUI.undo_manager.push_without_execute(
            ReorderFavoritesCommand(self.rootGUI, old_fav_orders, new_fav_orders, node)
        )

        # Refresh favorite tree display
        self.populate(self.rootGUI.main_tree, overwrite=True)

        # Restore selection
        self.selection_set(node)
        self.see(node)

        # Update button states
        self.rootGUI.sync_buttons_fav()

    def moveUp(self, *args):
        """Override to only reorder favorites without affecting main tree structure"""
        selection = self.selection()
        if not selection:
            return

        node = selection[0] if isinstance(selection, tuple) else selection

        index = self.index(node)
        if index == 0:
            return  # Already at top

        all_favs = list(self.get_children(''))
        all_favs.pop(index)
        all_favs.insert(index - 1, node)

        self._reorder_favorites(all_favs, node)

    def moveDown(self, *args):
        """Override to only reorder favorites without affecting main tree structure"""
        selection = self.selection()
        if not selection:
            return

        node = selection[0] if isinstance(selection, tuple) else selection

        all_favs = list(self.get_children(''))
        index = self.index(node)
        if index >= len(all_favs) - 1:
            return  # Already at bottom

        all_favs.pop(index)
        all_favs.insert(index + 1, node)

        self._reorder_favorites(all_favs, node)


    def play_sound(self, event):
        if self.rootGUI.enable_audio:
            node = self.identify_row(event.y)
            self.rootGUI.audio_widget.Play()
 