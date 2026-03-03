# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.


import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
from PIL import Image, ImageEnhance, ImageTk
from PIL.ImageTk import PhotoImage
import os.path, zipfile, json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

from io_utils import read_merlin_playlist, write_merlin_playlist, export_merlin_to_zip, IsImageProgressive
from treeviews import MerlinMainTree, MerlinFavTree
from gui_actions import GUIActions, TwoButtonCancelDialog, create_tooltip, DND_AVAILABLE, DND_FILES
from undo_manager import UndoManager
from constants import (
    DEFAULT_PICS_ZIP, ZIP_PASSWORD, DEFAULT_WINDOW_SIZE, DEFAULT_WINDOW_POSITION,
    MAX_UNDO_STACK_SIZE, IMAGE_THUMBNAIL_SIZE
)
from lazy_loader import LazyImageLoader
from image_utils import ImageProcessor, TreeHelpers
try:
    from audio import AudioWidget
    enable_audio = True
except ImportError as error:
    enable_audio = False

class MerlinGUI(GUIActions):

    def __init__(self):
        # create root window - call parent class to properly initialize TkinterDnD if available
        super().__init__()
        self.title('MerlinClaudinator')
        self.load_image()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.sessionpath = ''
        self.sessionfile = None
        self.playlistpath = ''  # Initialize playlistpath
        self.has_unsaved_changes = False
        self.thumbnails = {}
        self.moveitem = tk.StringVar()
        self.src_widget = None
        self.save_cursor = self['cursor'] or ''
        self.enable_audio = enable_audio

        # Drag-and-drop visual feedback
        self._drop_indicator_line = None
        self._drop_highlight_item = None
        self._drop_zone = None  # 'top', 'center', 'bottom'

        # Initialize lazy image loader for performance (with GUI reference for LRU eviction)
        self.lazy_loader = LazyImageLoader(gui=self)
        logger.info("Lazy image loader initialized with LRU eviction")

        # Initialize undo/redo manager
        self.undo_manager = UndoManager(self, max_stack_size=MAX_UNDO_STACK_SIZE)


        
        # configure the grid layout
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.maxsize(width=screen_w, height=screen_h)
        self.geometry('{}x{}+{:g}+{:g}'.format(*DEFAULT_WINDOW_SIZE, *DEFAULT_WINDOW_POSITION))
        self.update()
        
        # Create menu
        top_menu = tk.Menu(self)
        self.config(menu=top_menu)
        file_menu = tk.Menu(top_menu, tearoff=False)
        top_menu.add_cascade(label='Fichier', underline=0, menu=file_menu)
        file_menu.add_command(label="Nouvelle session (Ctrl-n)", underline=0, command=self.new_session)
        file_menu.add_command(label="Ouvrir session (Ctrl-o)", underline=0, command=self.load_session)
        file_menu.add_command(label="Sauver session  (Ctrl-s)", underline=0, command=self.save_session)
        file_menu.add_command(label="Sauver session sous", underline=1, command=self.saveas_session)
        file_menu.add_separator()
        file_menu.add_command(label="Importer playlist/archive (Ctrl-i)", underline=0, command=self.import_playlist)
        file_menu.add_command(label="Exporter playlist (Ctrl-e)", underline=0, command=self.export_playlist)
        file_menu.add_command(label="Exporter archive (Ctrl-x)", underline=1, command=self.export_all_to_zip)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", underline=0, command=self.quit)

        # Create Edit menu for Undo/Redo
        edit_menu = tk.Menu(top_menu, tearoff=False)
        top_menu.add_cascade(label='Édition', underline=0, menu=edit_menu)
        edit_menu.add_command(label="Annuler (Ctrl-Z)", underline=0, command=self.undo_action, state='disabled')
        edit_menu.add_command(label="Rétablir (Ctrl-Y)", underline=0, command=self.redo_action, state='disabled')
        self.edit_menu = edit_menu

        # Create Help menu
        help_menu = tk.Menu(top_menu, tearoff=False)
        top_menu.add_cascade(label='Aide', underline=0, menu=help_menu)
        help_menu.add_command(label="Raccourcis clavier", command=self.show_shortcuts_dialog)
        help_menu.add_separator()
        help_menu.add_command(label="\u00C0 propos", command=self.show_about_dialog)

        self.grid_columnconfigure(0, weight=1)
        
        # Main paned window
        self.main_paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.grid(row=0, column=0, sticky='eswn')
        
        # Main tree area
        self.main_tree_area = tk.LabelFrame(self.main_paned_window, text="Playlist", width=450)
        self.main_tree_area.grid_rowconfigure(0, weight=1)
        self.main_tree_area.grid_columnconfigure(0, weight=0)  # Move buttons column (fixed width)
        self.main_tree_area.grid_columnconfigure(1, weight=1)  # Tree column (expandable)
        self.main_tree_area.grid_propagate(0)
        self.main_paned_window.add(self.main_tree_area)
        
        style = ttk.Style()
        style.configure("Treeview", rowheight=40)
        self.update()

        # Load edition icons (needed for move buttons in tree)
        self.edition_icons, self.use_edition_icons = self._load_edition_icons()

        self.make_main_tree(self.main_tree_area)

        # Control Frame
        self.control_frame = tk.Frame(self.main_paned_window, width=330)
        self.control_frame.grid_rowconfigure(2, weight=1)  # Favorite tree area row
        self.control_frame.grid_columnconfigure(0, weight=1)
        self.control_frame.grid_columnconfigure(1, weight=1)
        self.control_frame.grid_propagate(0)
        self.main_paned_window.add(self.control_frame, sticky="nsew")
        
        # Title / Sound
        self.title_label_frame = tk.LabelFrame(self.control_frame, text="Contenu", height=2, padx=5)
        self.title_label_frame.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.title_label_frame.grid_columnconfigure(0, weight=1)
        self.title_label_frame.grid_columnconfigure(1, weight=0)

        # Title entry field
        vcmd = (self.register(lambda s: len(s.encode('UTF-8'))<=66), '%P')
        self.title_entry = tk.Entry(self.title_label_frame, state='disabled', validate='key', validatecommand=vcmd)
        self.title_entry.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        self.title_entry.bind('<Return>', self.setTitle)
        self.title_entry.bind('<KeyRelease>', self.sync_title_button)

        # Validate button with icon on the right
        title_bg = self.title_label_frame.cget('background')
        hover_bg = '#e5e5e5'

        if self.use_edition_icons:
            self.buttonSetTitle = tk.Button(self.title_label_frame, image=self.edition_icons['validate'],
                                           command=self.setTitle,
                                           relief='flat', bd=0, bg=title_bg, activebackground=hover_bg,
                                           highlightthickness=0)
        else:
            self.buttonSetTitle = tk.Button(self.title_label_frame, text="✓", font=("Arial", 14),
                                           command=self.setTitle,
                                           relief='flat', bd=0, bg=title_bg, fg='#666666',
                                           activebackground=hover_bg, highlightthickness=0)

        self.buttonSetTitle.grid(row=0, column=1, sticky='e')

        # Setup hover effects and tooltip
        if self.use_edition_icons:
            self._setup_icon_button_hover(self.buttonSetTitle, title_bg, hover_bg)
            self._create_tooltip(self.buttonSetTitle, "Mettre à jour le titre")

        # Initially hide the validate button
        self.buttonSetTitle.grid_remove()

        # Thumbnail Preview
        self.thumbnail_preview_frame = tk.Frame(self.title_label_frame, bg='#e0e0e0', relief='sunken', bd=2, height=220)
        self.thumbnail_preview_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        self.thumbnail_preview_frame.grid_propagate(False)  # Don't shrink to fit content
        self.thumbnail_preview_label = tk.Label(self.thumbnail_preview_frame, text="Aucune vignette\n(Cliquer pour changer l'image)",
                                                bg='#f5f5f5', fg='#666', font=('Arial', 9, 'italic'),
                                                relief='flat', cursor='hand2')
        self.thumbnail_preview_label.pack(expand=True, fill='both', padx=5, pady=5)
        self.current_thumbnail_photo = None  # Keep reference to prevent garbage collection

        # Click to change image
        self.thumbnail_preview_label.bind('<Button-1>', lambda e: self.main_tree.select_image())

        # Hover effects
        self.thumbnail_preview_label.bind('<Enter>', lambda e: self.thumbnail_preview_label.config(bg='#e8e8e8'))
        self.thumbnail_preview_label.bind('<Leave>', lambda e: self.thumbnail_preview_label.config(bg='#f5f5f5'))

        # Enable drag-and-drop for JPG files (if tkinterdnd2 is available)
        try:
            from gui_actions import DND_AVAILABLE, DND_FILES
            logger.debug("DND_AVAILABLE = %s", DND_AVAILABLE)
            if DND_AVAILABLE:
                self.thumbnail_preview_label.drop_target_register(DND_FILES)
                self.thumbnail_preview_label.dnd_bind('<<Drop>>', self.handle_thumbnail_drop)
                logger.info("Drag-and-drop enabled for thumbnail preview")
            else:
                logger.info("tkinterdnd2 not available - drag-and-drop disabled")
        except Exception as e:
            logger.warning("Could not enable drag-and-drop: %s", e)

        # Audio
        if self.enable_audio:
            self.audio_widget = AudioWidget(self.title_label_frame, self)
            self.audio_widget.grid(row=2, column=0, columnspan=2, sticky='ew')
            self.bind("<space>", self.audio_widget.PlayPause)

        # Favorite tree area
        self.fav_tree_area = tk.LabelFrame(self.control_frame, text="Favoris", width=200)
        self.fav_tree_area.grid_rowconfigure(0, weight=1)
        self.fav_tree_area.grid_columnconfigure(0, weight=0)  # Buttons column (fixed width)
        self.fav_tree_area.grid_columnconfigure(1, weight=1)  # Tree column (expandable)
        self.fav_tree_area.grid(row=2, column=0, columnspan=2, sticky='nsew')
        self.fav_tree_area.grid_propagate(0)
        self.make_fav_tree(self.fav_tree_area)

        self.update()
        
        
        self.bind("<BackSpace>", self.main_tree.deleteNode)
        self.bind("<Delete>", self.main_tree.deleteNode)
        
        self.bind("<Control-o>", lambda event:self.load_session())
        self.bind("<Control-s>", lambda event:self.save_session())
        self.bind("<Control-n>", lambda event:self.new_session())
        self.bind("<Control-i>", lambda event:self.import_playlist())
        self.bind("<Control-e>", lambda event:self.export_playlist())
        self.bind("<Control-x>", lambda event:self.export_all_to_zip())

        # Undo/Redo keyboard shortcuts
        self.bind("<Control-z>", lambda event:self.undo_action())
        self.bind("<Control-y>", lambda event:self.redo_action())

    def _load_edition_icons(self):
        """Load icon images for edition and move buttons from src directory."""
        icons = {}
        try:
            src_dir = Path(__file__).parent
            icons_dir = src_dir / 'icons'
            icon_files = {
                'new_folder': 'NewFolder.png',
                'add_album': 'AddAlbum.png',
                'new_song': 'NewSong.png',
                'delete': 'delete.png',
                'move_up': 'MoveUp.png',
                'move_down': 'MoveDown.png',
                'move_side': 'MoveSide.png',
                'validate': 'Validate.png',
                'favorite': 'Favorite.png'
            }

            scale_factor = 0.4  # Scale to 40%
            brightness_factor = 0.15  # Darken to 15%

            for key, filename in icon_files.items():
                icon_path = icons_dir / filename
                img = Image.open(icon_path).convert('RGBA')

                # Scale down to 40%
                new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
                img = img.resize(new_size, Image.LANCZOS)

                # Don't darken the favorite icon - keep it at full brightness
                if key != 'favorite':
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(brightness_factor)

                icons[key] = ImageTk.PhotoImage(img)

            # Create an empty/transparent icon for non-favorite items
            # Use a very low opacity version of the favorite icon
            icon_path = icons_dir / 'Favorite.png'
            img = Image.open(icon_path).convert('RGBA')
            new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
            img = img.resize(new_size, Image.LANCZOS)
            # Make it very transparent (30% brightness, 30% opacity)
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(0.3)
            # Reduce alpha channel
            data = img.getdata()
            new_data = []
            for item in data:
                new_data.append((item[0], item[1], item[2], int(item[3] * 0.3)))
            img.putdata(new_data)
            icons['favorite_empty'] = ImageTk.PhotoImage(img)

            logger.debug("Loaded edition icons successfully")
            return icons, True

        except Exception as e:
            logger.error("Failed to load edition icon images: %s", e)
            return {}, False

    def _setup_icon_button_hover(self, button, normal_bg, hover_bg='#e5e5e5'):
        """Setup hover effect for icon button - darken background on hover."""
        def on_enter(event):
            if button['state'] != 'disabled':
                button.config(bg=hover_bg)

        def on_leave(event):
            button.config(bg=normal_bg)

        button.bind('<Enter>', on_enter, add='+')
        button.bind('<Leave>', on_leave, add='+')

    def _create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget — delegates to standalone create_tooltip()"""
        create_tooltip(widget, text)


    def make_main_tree(self, parent):
        # Create buttons frame on the left
        self.move_buttons_frame = tk.Frame(parent, bg=parent.cget('background'))
        self.move_buttons_frame.grid(row=0, column=0, sticky='ns', padx=(5, 0))

        # Create buttons with icon style
        move_bg = self.move_buttons_frame.cget('background')
        hover_bg = '#e5e5e5'

        if self.use_edition_icons:
            # Edition buttons (always visible)
            self.buttonAddMenu = tk.Button(self.move_buttons_frame, image=self.edition_icons['new_folder'],
                                          state='disabled', command=lambda: self.main_tree.add_menu(),
                                          relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                          highlightthickness=0)
            self.buttonAddAlbum = tk.Button(self.move_buttons_frame, image=self.edition_icons['add_album'],
                                           state='disabled', command=lambda: self.main_tree.add_album(),
                                           relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                           highlightthickness=0)
            self.buttonAddSound = tk.Button(self.move_buttons_frame, image=self.edition_icons['new_song'],
                                           state='disabled', command=lambda: self.main_tree.add_sound(),
                                           relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                           highlightthickness=0)
            self.buttonDelete = tk.Button(self.move_buttons_frame, image=self.edition_icons['delete'],
                                         state='disabled', command=lambda: self.main_tree.deleteNode(),
                                         relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                         highlightthickness=0)

            # Move buttons (show/hide based on selection)
            self.buttonMoveUp = tk.Button(self.move_buttons_frame, image=self.edition_icons['move_up'],
                                         state='disabled', command=lambda: self.main_tree.moveUp(),
                                         relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                         highlightthickness=0)
            self.buttonMoveParentDir = tk.Button(self.move_buttons_frame, image=self.edition_icons['move_side'],
                                                state='disabled', command=lambda: self.main_tree.moveParentDir(),
                                                relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                                highlightthickness=0)
            self.buttonMoveDown = tk.Button(self.move_buttons_frame, image=self.edition_icons['move_down'],
                                           state='disabled', command=lambda: self.main_tree.moveDown(),
                                           relief='flat', bd=0, bg=move_bg, activebackground=hover_bg,
                                           highlightthickness=0)
        else:
            # Fallback to text buttons
            self.buttonAddMenu = tk.Button(self.move_buttons_frame, text="M", width=3, state='disabled', command=lambda: self.main_tree.add_menu())
            self.buttonAddAlbum = tk.Button(self.move_buttons_frame, text="A", width=3, state='disabled', command=lambda: self.main_tree.add_album())
            self.buttonAddSound = tk.Button(self.move_buttons_frame, text="S", width=3, state='disabled', command=lambda: self.main_tree.add_sound())
            self.buttonDelete = tk.Button(self.move_buttons_frame, text="X", width=3, state='disabled', command=lambda: self.main_tree.deleteNode())

            self.buttonMoveUp = tk.Button(self.move_buttons_frame, text="\u21D1", width=3, state='disabled', command=lambda: self.main_tree.moveUp())
            self.buttonMoveParentDir = tk.Button(self.move_buttons_frame, text="\u21D0", width=3, state='disabled', command=lambda: self.main_tree.moveParentDir())
            self.buttonMoveDown = tk.Button(self.move_buttons_frame, text="\u21D3", width=3, state='disabled', command=lambda: self.main_tree.moveDown())

        # Pack edition buttons first
        self.buttonAddMenu.pack(pady=(0, 5))
        self.buttonAddAlbum.pack(pady=(0, 5))
        self.buttonAddSound.pack(pady=(0, 5))
        self.buttonDelete.pack(pady=(0, 15))  # Extra space before move buttons

        # Pack move buttons
        self.buttonMoveUp.pack(pady=(0, 5))
        self.buttonMoveParentDir.pack(pady=(0, 5))
        self.buttonMoveDown.pack()

        # Setup hover effects and tooltips
        if self.use_edition_icons:
            # Edition buttons
            self._setup_icon_button_hover(self.buttonAddMenu, move_bg, hover_bg)
            self._setup_icon_button_hover(self.buttonAddAlbum, move_bg, hover_bg)
            self._setup_icon_button_hover(self.buttonAddSound, move_bg, hover_bg)
            self._setup_icon_button_hover(self.buttonDelete, move_bg, hover_bg)

            self._create_tooltip(self.buttonAddMenu, "Nouveau Menu")
            self._create_tooltip(self.buttonAddAlbum, "Ajouter Album")
            self._create_tooltip(self.buttonAddSound, "Nouveau Son")
            self._create_tooltip(self.buttonDelete, "Supprimer")

            # Move buttons
            self._setup_icon_button_hover(self.buttonMoveUp, move_bg, hover_bg)
            self._setup_icon_button_hover(self.buttonMoveParentDir, move_bg, hover_bg)
            self._setup_icon_button_hover(self.buttonMoveDown, move_bg, hover_bg)

            self._create_tooltip(self.buttonMoveUp, "Déplacer vers le haut")
            self._create_tooltip(self.buttonMoveParentDir, "Déplacer vers le dossier parent")
            self._create_tooltip(self.buttonMoveDown, "Déplacer vers le bas")

        # Create tree in column 1
        self.main_tree = MerlinMainTree(parent, self)
        main_tree = self.main_tree
        main_tree.grid(row=0, column=1, sticky='nsew')

        self.scroll_my = tk.Scrollbar(parent, orient=tk.VERTICAL)
        self.scroll_my.grid(row=0, column=2, sticky=tk.N+tk.S)
        main_tree['yscrollcommand']=self.scroll_my.set
        self.scroll_my.config( command = main_tree.yview )
        self.scroll_mx = tk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.main_tree.xview)
        self.scroll_mx.grid(row=1, column=1, sticky=tk.E+tk.W)
        main_tree['xscrollcommand']=self.scroll_mx.set
        self.scroll_mx.config( command = main_tree.xview )

        # Bind events for lazy loading
        main_tree.bind('<<TreeviewOpen>>', lambda e: self.after(50, self.load_visible_thumbnails))
        main_tree.bind('<MouseWheel>', lambda e: self.after(200, self.load_visible_thumbnails))
        
    
    def make_fav_tree(self, parent):
        # Create buttons frame on the left
        self.fav_buttons_frame = tk.Frame(parent, bg=parent.cget('background'))
        self.fav_buttons_frame.grid(row=0, column=0, sticky='ns', padx=(5, 0))

        # Create buttons with icon style
        fav_bg = self.fav_buttons_frame.cget('background')
        hover_bg = '#e5e5e5'

        if self.use_edition_icons:
            self.buttonMoveUpFav = tk.Button(self.fav_buttons_frame, image=self.edition_icons['move_up'],
                                            state='disabled', command=lambda: self.fav_tree.moveUp(),
                                            relief='flat', bd=0, bg=fav_bg, activebackground=hover_bg,
                                            highlightthickness=0)
            self.buttonMoveDownFav = tk.Button(self.fav_buttons_frame, image=self.edition_icons['move_down'],
                                              state='disabled', command=lambda: self.fav_tree.moveDown(),
                                              relief='flat', bd=0, bg=fav_bg, activebackground=hover_bg,
                                              highlightthickness=0)
        else:
            self.buttonMoveUpFav = tk.Button(self.fav_buttons_frame, text="\u21D1", width=3, state='disabled', command=lambda: self.fav_tree.moveUp())
            self.buttonMoveDownFav = tk.Button(self.fav_buttons_frame, text="\u21D3", width=3, state='disabled', command=lambda: self.fav_tree.moveDown())

        self.buttonMoveUpFav.pack(pady=(0, 5))
        self.buttonMoveDownFav.pack()

        # Setup hover effects and tooltips
        if self.use_edition_icons:
            self._setup_icon_button_hover(self.buttonMoveUpFav, fav_bg, hover_bg)
            self._setup_icon_button_hover(self.buttonMoveDownFav, fav_bg, hover_bg)

            self._create_tooltip(self.buttonMoveUpFav, "Déplacer vers le haut")
            self._create_tooltip(self.buttonMoveDownFav, "Déplacer vers le bas")

        # Create tree in column 1
        self.fav_tree = MerlinFavTree(parent, self)
        fav_tree = self.fav_tree
        fav_tree.grid(row=0, column=1, sticky='nsew')

        self.scroll_fy = tk.Scrollbar(parent, orient=tk.VERTICAL)
        self.scroll_fy.grid(row=0, column=2, sticky=tk.N+tk.S)
        fav_tree['yscrollcommand']=self.scroll_fy.set
        self.scroll_fy.config( command = fav_tree.yview )
        self.scroll_fx = tk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.fav_tree.xview)
        self.scroll_fx.grid(row=1, column=1, sticky=tk.E+tk.W)
        fav_tree['xscrollcommand']=self.scroll_fx.set
        self.scroll_fx.config( command = fav_tree.xview )

        # Bind events for lazy loading
        fav_tree.bind('<<TreeviewOpen>>', lambda e: self.after(50, self.load_visible_thumbnails))
        fav_tree.bind('<MouseWheel>', lambda e: self.after(200, self.load_visible_thumbnails))
        

    def populate_trees(self, items, overwrite=True):
        self.main_tree.populate(items, self.thumbnails, overwrite)
        self.fav_tree.populate(self.main_tree, overwrite)
        if overwrite:
            self.undo_manager.clear()
            self.update_undo_menu_state()

        # Trigger lazy loading for visible items
        self.after(100, self.load_visible_thumbnails)
        

    def load_visible_thumbnails(self):
        """Load thumbnails for currently visible tree items."""
        try:
            # Get visible items from main tree
            visible_uuids = self._get_visible_uuids(self.main_tree)

            # Get visible items from favorites tree
            visible_uuids.update(self._get_visible_uuids(self.fav_tree))

            # Load thumbnails for visible items
            loaded_count = 0
            for uuid in visible_uuids:
                # Load if not in thumbnails or is empty (evicted or never loaded)
                if uuid not in self.thumbnails or not self.thumbnails[uuid]:
                    # Load thumbnail
                    thumbnail = self.lazy_loader.get_thumbnail(uuid, self)
                    if thumbnail:
                        self.thumbnails[uuid] = thumbnail
                        loaded_count += 1

                        # Update tree items with the loaded thumbnail
                        self._update_tree_item_image(self.main_tree, uuid, thumbnail)
                        self._update_tree_item_image(self.fav_tree, uuid, thumbnail)

            if loaded_count > 0:
                logger.debug("Lazy loaded %d thumbnails", loaded_count)
                # Log cache stats periodically to track LRU eviction
                if loaded_count > 10:
                    self.lazy_loader.log_stats()

        except Exception as e:
            logger.error("Error loading visible thumbnails: %s", e)

    def _get_visible_uuids(self, tree):
        """Get UUIDs of visible items in a tree."""
        visible_uuids = set()

        try:
            # Use TreeHelpers utility
            visible_items = TreeHelpers.collect_visible_items(tree, '', check_expanded=True)

            for item_id in visible_items:
                try:
                    uuid = tree.set(item_id, 'uuid')
                    if uuid:
                        visible_uuids.add(uuid)
                except tk.TclError:
                    pass

        except Exception as e:
            logger.error("Error getting visible UUIDs: %s", e)

        return visible_uuids

    def _update_tree_item_image(self, tree, uuid, thumbnail):
        """Update tree item with loaded thumbnail."""
        try:
            # Use TreeHelpers utility
            return TreeHelpers.update_item_image_by_uuid(tree, uuid, thumbnail)
        except Exception as e:
            logger.error("Error updating tree item image: %s", e)
            return False

    def load_thumbnails(self, items, overwrite=True, zfile=None):
        """Register thumbnails for lazy loading.

        Args:
            items: List of item dicts with 'uuid' keys
            overwrite: Clear existing thumbnails first
            zfile: If provided (ZipFile object), register from ZIP archive;
                   otherwise register from file paths
        """
        if overwrite:
            self.thumbnails = {}
            self.lazy_loader.clear_cache()

        # Register items with lazy loader
        if zfile:
            zipfile_path = zfile.filename
            self.lazy_loader.register_items_from_zip(items, zipfile_path)
            logger.info("Registered %d thumbnails from ZIP for lazy loading", len(items))
        else:
            self.lazy_loader.register_items_from_list(items)
            logger.info("Registered %d thumbnails for lazy loading", len(items))

        # Initialize empty placeholders in thumbnails dict
        for item in items:
            if item['uuid'] not in self.thumbnails:
                self.thumbnails[item['uuid']] = ''    
                
    def load_image(self):
        filename = "merlinator_64px.ico"
        with zipfile.ZipFile(DEFAULT_PICS_ZIP, 'r') as zfile:
            zippath = zipfile.Path(zfile, at=filename)
            if zippath.exists():
                with zfile.open(filename, 'r', pwd=ZIP_PASSWORD) as imagefile:
                    with Image.open(imagefile) as image:
                        self.iconphoto(False, PhotoImage(image))



    def import_playlist(self):
        filepath = filedialog.askopenfilename(initialfile="playlist.bin", filetypes=[('tous types supportés', '*.bin;*.zip'), ('binaire', '*.bin'), ('fichier zip', '*.zip')])
        if not filepath:
            return
        
        overwrite = True
        if self.main_tree.get_children():
            dialog = TwoButtonCancelDialog(title="Combiner ou écraser?", parent=self, \
                                            prompt="Écraser la playlist courante, ou combiner les playlists?", \
                                            button0text="Combiner", button1text="Écraser")
            if dialog.res == 2:
                return
            elif dialog.res == 0:
                overwrite = False
        if overwrite:
            self.playlistpath = filepath
        try: 
            if filepath[-3:] == "bin":
                dirname = os.path.dirname(filepath)
                with open(filepath, "rb") as file:
                    items = read_merlin_playlist(file)
                    for item in items:
                        if item['type'] == 1: # root
                            item['imagepath'] = ''
                        else:
                            item['imagepath'] = os.path.join(dirname, item['uuid'] + '.jpg')
                        if item['type'] in [4, 36]:
                            soundpath = os.path.join(dirname, item['uuid'] + '.mp3')
                            item['soundpath'] = soundpath
                        else:
                            item['soundpath'] = ''
                    self.load_thumbnails(items, overwrite)
            elif filepath[-3:] == "zip":
                with zipfile.ZipFile(filepath, 'r') as z:
                    with z.open("playlist.bin", "r") as file:
                        items = read_merlin_playlist(file)
                    for item in items:
                        item['imagepath'] = filepath
                        if item['type'] in [4, 36]:
                            item['soundpath'] = filepath
                        else:
                            item['soundpath'] = ''
                    self.load_thumbnails(items, overwrite, zfile=z)
            self.populate_trees(items, overwrite)
            self.buttonAddMenu['state'] = 'normal'
            self.buttonAddSound['state'] = 'normal'
            self.buttonAddAlbum['state'] = 'normal'
        except IOError:
            tk.messagebox.showwarning("Erreur", "Fichier non accessible")
          
          
    def export_playlist(self):
        t = self.main_tree
        if not t.get_children(''):
            return
        filepath = filedialog.asksaveasfilename(initialfile="playlist.bin", filetypes=[('binaire', '*.bin')])
        try:
            with open(filepath, "wb") as file:
                items = t.make_item_list()
                write_merlin_playlist(file, items)
        except IOError:
            tk.messagebox.showwarning("Erreur", "Fichier non accessible")     
   

    def export_all_to_zip(self):
        t = self.main_tree
        if not t.get_children(''):
            return
        filepath = filedialog.asksaveasfilename(initialfile="merlin.zip", filetypes=[('archive zip', '*.zip')])
        try:
            with zipfile.ZipFile(filepath, 'w') as zfile:
                items = self.main_tree.make_item_list()
                files_not_found = export_merlin_to_zip(items, zfile)
            if files_not_found:
                message = "Les fichiers suivants n'ont pas été trouvés:\n" + "\n".join([f"- '{f}'" for f in files_not_found])
                tk.messagebox.showwarning("Fichiers non trouvés", message)
        except IOError:
            tk.messagebox.showwarning("Erreur", "Fichier non accessible")
        
    def new_session(self):
        items = MerlinMainTree.defaultItems
        with zipfile.ZipFile(DEFAULT_PICS_ZIP, 'r') as zfile:
            self.load_thumbnails(items, zfile=zfile)
        self.populate_trees(items, overwrite=True)
        self.undo_manager.clear()
        self.update_undo_menu_state()
        self.buttonAddMenu['state'] = 'normal'
        self.buttonAddSound['state'] = 'normal'
        self.buttonAddAlbum['state'] = 'normal'
        
    def save_session(self):
        if not self.sessionfile:
            self.saveas_session()
            return
        elif not self.main_tree.get_children(''):
            return
        if self.sessionfile and not self.sessionfile.closed:
            self.sessionfile.close()
        try:
            with open(self.sessionpath, 'wb') as f:
                items = self.main_tree.make_item_list()
                f.write(json.dumps(items, indent=2).encode("utf-8"))
            self.sessionfile = open(self.sessionpath, 'rb')
            self.has_unsaved_changes = False
        except IOError:
            logger.error("Failed to save session to %s", self.sessionpath)
            tk.messagebox.showwarning("Erreur", "Impossible de sauvegarder le fichier")

    def saveas_session(self):
        if not self.main_tree.get_children(''):
            return
        filepath = filedialog.asksaveasfilename(initialfile="merlinator.json", filetypes=[('fichier json', '*.json')])
        if not filepath:
            return
        try:
            # Verify we can write to the path
            with open(filepath, 'w') as f:
                pass
            if self.sessionfile and not self.sessionfile.closed:
                self.sessionfile.close()
            self.sessionpath = filepath
            self.sessionfile = open(filepath, 'rb')
            self.save_session()
        except IOError:
            tk.messagebox.showwarning("Erreur", "Fichier non accessible")


    def load_session(self):
        filepath = filedialog.askopenfilename(initialfile="merlinator.json", filetypes=[('fichier json', '*.json')])
        if not filepath:
            return
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            items = json.loads(content)
        except IOError:
            tk.messagebox.showwarning("Erreur", "Fichier non accessible")
            return
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Invalid JSON in session file %s: %s", filepath, e)
            tk.messagebox.showwarning("Erreur", "Le fichier de session est corrompu ou invalide.\n%s" % e)
            return

        self.sessionpath = filepath
        self.sessionfile = open(filepath, 'rb')
        self.load_thumbnails(items)
        self.populate_trees(items)
        self.undo_manager.clear()
        self.has_unsaved_changes = False
        self.update_undo_menu_state()
        self.buttonAddMenu['state'] = 'normal'
        self.buttonAddSound['state'] = 'normal'
        self.buttonAddAlbum['state'] = 'normal'
        

        
    def clear_temp_variables(self, event=None):
        self.moveitem.set('')
        self.src_widget = None

    def mouseclick(self, event):
        t = event.widget
        if t.identify_region(event.x, event.y) == "tree":
            self.moveitem.set(t.identify_row(event.y))

    def _get_drop_zone(self, tree, event_y, item):
        """Determine drop zone: 'top' (insert before), 'center' (drop into), 'bottom' (insert after)"""
        if not item:
            return None
        try:
            bbox = tree.bbox(item)
            if not bbox:
                return 'center'
            item_y, item_height = bbox[1], bbox[3]
            relative_y = event_y - item_y
            # Top 25% = insert before, Bottom 25% = insert after, Middle 50% = drop into
            if relative_y < item_height * 0.25:
                return 'top'
            elif relative_y > item_height * 0.75:
                return 'bottom'
            else:
                return 'center'
        except tk.TclError:
            return 'center'

    def _clear_drop_feedback(self):
        """Clear all drag-and-drop visual feedback"""
        if self._drop_indicator_line:
            self._drop_indicator_line.destroy()
            self._drop_indicator_line = None
        if self._drop_highlight_item:
            try:
                self.main_tree.tag_configure('drop_highlight', background='')
                self.main_tree.item(self._drop_highlight_item, tags=
                    [t for t in self.main_tree.item(self._drop_highlight_item, 'tags') if t != 'drop_highlight'])
            except tk.TclError:
                pass
            self._drop_highlight_item = None
        self._drop_zone = None

    def _show_drop_feedback(self, tree, item, zone):
        """Show visual feedback for drop location"""
        self._clear_drop_feedback()
        if not item:
            return

        try:
            bbox = tree.bbox(item)
            if not bbox:
                return

            tree_x = tree.winfo_rootx()
            tree_y = tree.winfo_rooty()
            item_x, item_y, item_width, item_height = bbox

            if zone in ('top', 'bottom'):
                # Show insertion line
                line_y = item_y if zone == 'top' else item_y + item_height
                self._drop_indicator_line = tk.Frame(tree, height=2, bg='#0078D7')
                self._drop_indicator_line.place(x=item_x, y=line_y, width=item_width)
            else:
                # Highlight folder for drop-into
                tree.tag_configure('drop_highlight', background='#CCE8FF')
                current_tags = list(tree.item(item, 'tags'))
                if 'drop_highlight' not in current_tags:
                    current_tags.append('drop_highlight')
                    tree.item(item, tags=current_tags)
                self._drop_highlight_item = item

            self._drop_zone = zone
        except tk.TclError:
            pass

    def movemouse(self, event):
        t = event.widget
        self.src_widget = t
        self.save_cursor = t['cursor'] or ''
        if self.moveitem.get():
            t['cursor'] = "hand2"
            # Show drop feedback when dragging over main_tree
            if t == self.main_tree:
                dest_item = t.identify_row(event.y)
                src = self.moveitem.get()
                if dest_item and dest_item != src:
                    dest_type = t.set(dest_item, "type")
                    # Only show zone feedback for folders
                    if dest_type not in ['4', '36']:
                        zone = self._get_drop_zone(t, event.y, dest_item)
                        self._show_drop_feedback(t, dest_item, zone)
                    else:
                        self._clear_drop_feedback()
                else:
                    self._clear_drop_feedback()
            
    
    def mouserelease(self, event):
        t = event.widget
        t['cursor'] = self.save_cursor

        # Store drop zone before clearing feedback
        drop_zone = self._drop_zone
        self._clear_drop_feedback()

        try:
            x = event.x+t.winfo_rootx()
            y = event.y+t.winfo_rooty()
            x0 = self.main_tree.winfo_rootx()
            x1 = x0 + self.main_tree.winfo_width()
            y0 = self.main_tree.winfo_rooty()
            y1 = y0 + self.main_tree.winfo_height()
            if x0<=x<=x1 and y0<=y<=y1:
                t = self.main_tree
            else:
                x0 = self.fav_tree.winfo_rootx()
                x1 = x0 + self.fav_tree.winfo_width()
                y0 = self.fav_tree.winfo_rooty()
                y1 = y0 + self.fav_tree.winfo_height()
                if x0<=x<=x1 and y0<=y<=y1:
                    t = self.fav_tree
                else:
                    t = None
            moveitem = self.moveitem
            src = moveitem.get()
            new_pos = None

            # Capture state before drag-and-drop operation (for undo)
            before_snapshot = None
            if src and t:
                before_snapshot = self.undo_manager.create_tree_snapshot()

            if src:
                if t == self.src_widget:
                    if t == self.main_tree:
                        if t.identify_region(event.x, event.y) == "tree":
                            dest = t.identify_row(event.y)
                        elif t.identify_column(event.x) == '#0':
                            dest = ''
                            if event.y<0 or (t.identify_region(event.x, event.y) in ["heading", "separator"]):
                                new_pos = 0
                            else:
                                new_pos = 'end'
                        else:
                            dest = src
                        if new_pos is None:
                            if t.set(dest, "type") in ['4', '36']: # destination is a file
                                if t.parent(dest)==t.parent(src) and t.index(dest)>=t.index(src):
                                    new_pos = t.index(dest)
                                else:
                                    new_pos = t.index(dest)+1
                                dest = t.parent(dest)
                            else: # destination is a folder
                                # Use drop zone to determine action
                                # Recalculate zone if not set (e.g., quick release)
                                if drop_zone is None:
                                    drop_zone = self._get_drop_zone(t, event.y, dest)

                                if drop_zone in ('top', 'bottom'):
                                    # Insert before/after the target folder (reorder)
                                    if drop_zone == 'top':
                                        new_pos = t.index(dest)
                                    else:  # bottom
                                        new_pos = t.index(dest) + 1
                                    # Adjust position if moving within same parent
                                    if t.parent(src) == t.parent(dest) and t.index(src) < t.index(dest):
                                        new_pos -= 1
                                    dest = t.parent(dest)
                                else:
                                    # Drop INTO the folder (center zone)
                                    new_pos = 0

                        if src in t.get_ancestors(dest): # destination is descendant of source
                            pass
                        elif t.set(src, "type") in ['4', '36']: # source is a file
                            if src==dest:
                                pass
                            else:
                                t.move(src, dest, new_pos)
                                t.see(src)
                                # Expand parent folder and refresh thumbnails
                                if dest:
                                    t.item(dest, open=True)
                                self.after(100, self.load_visible_thumbnails)
                        elif t.set(src, "type") in ['2', '34']: # source is a directory
                            iid = t.insert(dest, new_pos, text=t.item(src, "text"),
                                          values=t.item(src, "values"), image=t.item(src, "image"),
                                          tags=t.item(src, "tags"))
                            t.set_children(iid, *t.get_children(src))
                            t.delete(src)
                            t.see(iid)
                            # Expand parent folder and refresh thumbnails
                            if dest:
                                t.item(dest, open=True)
                            self.after(100, self.load_visible_thumbnails)
                        else: # shouldn't happen
                            pass
                        self.sync_buttons_main()
                    elif t == self.fav_tree:
                        if t.identify_region(event.x, event.y) == "tree":
                            new_pos = t.index(t.identify_row(event.y))
                        elif t.identify_column(event.x) == '#0':
                            if event.y<0 or (t.identify_region(event.x, event.y) in ["heading", "separator"]):
                                new_pos = 0
                            else:
                                new_pos = 'end'
                        if new_pos is not None:
                            self.fav_tree.move(src, '', new_pos)
                        self.sync_buttons_main()
                elif self.src_widget == self.main_tree and t == self.fav_tree:
                    dest_x = event.x+event.widget.winfo_rootx()-t.winfo_rootx()
                    dest_y = event.y+event.widget.winfo_rooty()-t.winfo_rooty()
                    if t.identify_region(dest_x, dest_y) == "tree":
                        new_pos = t.index(t.identify_row(dest_y))+1
                    elif t.identify_column(dest_x) == '#0':
                        if event.y<0 or (t.identify_region(dest_x, dest_y) in ["heading", "separator"]):
                            new_pos = 0
                        else:
                            new_pos = 'end'
                    if new_pos is not None:
                        self.main_tree.addToFavorite(src, new_pos)
                    self.src_widget.update()
                    self.sync_buttons_fav()
            if t:
                t.update()

            # Capture state after drag-and-drop and create undo command
            if before_snapshot is not None:
                after_snapshot = self.undo_manager.create_tree_snapshot()
                # Check if anything actually changed
                if before_snapshot != after_snapshot:
                    from undo_manager import DragDropCommand
                    self.undo_manager.push_without_execute(
                        DragDropCommand(self, before_snapshot, after_snapshot)
                    )
        except Exception as e:
            logger.error("Error during drag-and-drop: %s", e, exc_info=True)
        finally:
            self.moveitem.set("")
            self.src_widget = None

    def undo_action(self):
        """Perform undo operation"""
        if self.undo_manager.can_undo():
            self.undo_manager.undo()
            self.update_undo_menu_state()
            self.sync_buttons_main()
            self.sync_buttons_fav()
            self.clear_temp_variables()  # Clear drag state to prevent stale IID errors

    def redo_action(self):
        """Perform redo operation"""
        if self.undo_manager.can_redo():
            self.undo_manager.redo()
            self.update_undo_menu_state()
            self.sync_buttons_main()
            self.sync_buttons_fav()
            self.clear_temp_variables()  # Clear drag state to prevent stale IID errors

    def update_undo_menu_state(self):
        """Update undo/redo menu item states and labels"""
        # Update undo menu item
        if self.undo_manager.can_undo():
            last_cmd = self.undo_manager.undo_stack[-1]
            label = f"Annuler {last_cmd.get_description()} (Ctrl-Z)"
            self.edit_menu.entryconfig(0, label=label, state='normal')
        else:
            self.edit_menu.entryconfig(0, label="Annuler (Ctrl-Z)", state='disabled')

        # Update redo menu item
        if self.undo_manager.can_redo():
            next_cmd = self.undo_manager.redo_stack[-1]
            label = f"Rétablir {next_cmd.get_description()} (Ctrl-Y)"
            self.edit_menu.entryconfig(1, label=label, state='normal')
        else:
            self.edit_menu.entryconfig(1, label="Rétablir (Ctrl-Y)", state='disabled')

    def show_shortcuts_dialog(self):
        """Show a dialog listing all keyboard shortcuts"""
        dialog = tk.Toplevel(self)
        dialog.title("Raccourcis clavier")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()

        # Center on parent
        dialog.geometry("+%d+%d" % (
            self.winfo_rootx() + 100,
            self.winfo_rooty() + 50
        ))

        shortcuts = [
            ("Fichier", [
                ("Ctrl+N", "Nouvelle session"),
                ("Ctrl+O", "Ouvrir session"),
                ("Ctrl+S", "Sauver session"),
                ("Ctrl+I", "Importer playlist/archive"),
                ("Ctrl+E", "Exporter playlist"),
                ("Ctrl+X", "Exporter archive"),
            ]),
            ("\u00C9dition", [
                ("Ctrl+Z", "Annuler"),
                ("Ctrl+Y", "R\u00E9tablir"),
                ("Suppr / Retour", "Supprimer l'\u00E9l\u00E9ment"),
            ]),
            ("Navigation", [
                ("Ctrl+\u2191", "D\u00E9placer vers le haut"),
                ("Ctrl+\u2193", "D\u00E9placer vers le bas"),
                ("Ctrl+\u2190", "D\u00E9placer vers le parent"),
            ]),
            ("Audio", [
                ("Espace", "Lecture / Pause"),
            ]),
        ]

        main_frame = tk.Frame(dialog, padx=20, pady=15)
        main_frame.pack(fill='both', expand=True)

        row = 0
        for category, bindings in shortcuts:
            # Category header
            header = tk.Label(main_frame, text=category, font=("Arial", 11, "bold"),
                              anchor='w')
            header.grid(row=row, column=0, columnspan=2, sticky='w', pady=(10 if row > 0 else 0, 4))
            row += 1

            for shortcut, action in bindings:
                key_label = tk.Label(main_frame, text=shortcut, font=("Arial", 10, "bold"),
                                     fg='#444', anchor='w', width=16)
                key_label.grid(row=row, column=0, sticky='w', padx=(15, 10), pady=1)

                action_label = tk.Label(main_frame, text=action, font=("Arial", 10),
                                        anchor='w')
                action_label.grid(row=row, column=1, sticky='w', pady=1)
                row += 1

        # Close button
        close_btn = tk.Button(dialog, text="Fermer", width=10,
                              command=dialog.destroy)
        close_btn.pack(pady=(5, 15))

        # Escape to close
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def show_about_dialog(self):
        """Show the About dialog"""
        tk.messagebox.showinfo(
            "\u00C0 propos",
            "MerlinClaudinator\n\n"
            "\u00C9diteur de playlist pour enceinte Merlin\n"
            "Bas\u00E9 sur Merlinator par Cyril Joder\n\n"
            "Licence MIT"
        )

    def handle_thumbnail_drop(self, event):
        """Handle drag-and-drop of image files onto thumbnail preview"""
        # Check if a node is selected
        selected_node = self.main_tree.selection()
        if not selected_node:
            tk.messagebox.showwarning("Pas de sélection", "Veuillez sélectionner un élément avant de déposer une image.")
            return

        # Get the dropped file path
        # event.data contains the file path(s), possibly in curly braces
        file_path = event.data

        # Remove curly braces if present (Windows style)
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]

        # Handle multiple files - take only the first
        if ' ' in file_path and not os.path.exists(file_path):
            file_path = file_path.split()[0]
            if file_path.startswith('{'):
                file_path = file_path[1:]
            if file_path.endswith('}'):
                file_path = file_path[:-1]

        logger.debug("Dropped file: %s", file_path)

        # Validate file exists
        if not os.path.exists(file_path):
            tk.messagebox.showerror("Fichier introuvable", f"Le fichier n'existe pas:\n{file_path}")
            return

        # Validate file is a JPG
        if not file_path.lower().endswith(('.jpg', '.jpeg')):
            tk.messagebox.showerror("Format invalide", "Seuls les fichiers JPG/JPEG sont supportés.\n\nAstuce: Convertissez votre image en JPG d'abord.")
            return

        # Check if Windows DnD created a temp copy in the playlist folder
        playlist_dir = os.path.dirname(self.playlistpath) if self.playlistpath else os.path.expanduser('~')
        dropped_file_dir = os.path.dirname(os.path.abspath(file_path))

        is_temp_copy = (os.path.abspath(dropped_file_dir) == os.path.abspath(playlist_dir))
        logger.debug("Dropped file dir: %s", dropped_file_dir)
        logger.debug("Playlist dir: %s", playlist_dir)
        logger.debug("Is temp DnD copy: %s", is_temp_copy)

        # Set the thumbnail from the dropped file
        self.set_thumbnail_from_file(selected_node[0], file_path, is_temp_dnd_copy=is_temp_copy)


    def set_thumbnail_from_file(self, node_iid, filepath, is_temp_dnd_copy=False):
        """Set thumbnail for a node from a file path with undo support

        Args:
            node_iid: The tree node ID
            filepath: Path to the image file
            is_temp_dnd_copy: True if Windows DnD already copied the file to playlist folder
        """
        # Check for progressive JPEG
        with open(filepath, 'rb') as stream:
            if IsImageProgressive(stream):
                answer = tk.messagebox.askyesno(
                    "Format JPEG progressif",
                    "Le format de l'image est JPEG 'progressive'.\n"
                    "Ce format n'est pas pris en charge par toutes les Merlin.\n\n"
                    "Continuer quand même?"
                )
                if not answer:
                    return

        # Get old state for undo
        old_imagepath = self.main_tree.set(node_iid, 'imagepath')
        old_uuid = self.main_tree.set(node_iid, 'uuid')
        old_thumbnail = self.thumbnails.get(old_uuid, '')

        # Generate a NEW UUID for the new image (don't reuse old one to preserve old file!)
        import uuid as uuid_module
        new_uuid = str(uuid_module.uuid4())

        # Copy/validate the image file
        playlist_dir = os.path.dirname(self.playlistpath) if self.playlistpath else os.path.expanduser('~')
        target_path = os.path.join(playlist_dir, new_uuid + '.jpg')

        logger.debug("Drag-drop: old_uuid=%s, new_uuid=%s", old_uuid, new_uuid)
        logger.debug("Drag-drop: old_imagepath=%s", old_imagepath)
        logger.debug("Drag-drop: target_path=%s", target_path)
        logger.debug("Drag-drop: source filepath=%s", filepath)
        logger.debug("Drag-drop: is_temp_dnd_copy=%s", is_temp_dnd_copy)

        # If this is a temp DnD copy, rename it instead of copying again
        if is_temp_dnd_copy:
            logger.debug("Renaming temp DnD copy to use new UUID...")
            # Use ImageProcessor utility
            if ImageProcessor.resize_for_storage(filepath, target_path):
                # Delete the temp copy
                os.remove(filepath)
                logger.info("Renamed temp copy to: %s", target_path)
                logger.info("Deleted temp copy: %s", filepath)
            else:
                tk.messagebox.showerror("Erreur", "Impossible de traiter l'image")
                return
        # If file is not already in playlist directory, copy it
        elif os.path.abspath(filepath) != os.path.abspath(target_path):
            logger.debug("Files are different, copying...")
            # Use ImageProcessor utility
            if ImageProcessor.resize_for_storage(filepath, target_path):
                logger.info("Image copied and resized to: %s", target_path)
            else:
                tk.messagebox.showerror("Erreur", "Impossible de traiter l'image")
                return
        else:
            logger.debug("Files are same, no copy needed")
            target_path = filepath

        # Load thumbnail into memory
        thumbnail = ImageProcessor.create_thumbnail_photoimage(target_path, IMAGE_THUMBNAIL_SIZE, check_progressive=False)
        if not thumbnail:
            tk.messagebox.showerror("Erreur", "Impossible de charger la vignette")
            return
        self.thumbnails[new_uuid] = thumbnail

        # Update tree view
        self.main_tree.item(node_iid, image=self.thumbnails[new_uuid])
        self.main_tree.set(node_iid, 'imagepath', target_path)
        self.main_tree.set(node_iid, 'uuid', new_uuid)

        # Create undo command
        from undo_manager import SelectImageCommand
        cmd = SelectImageCommand(self, node_iid, old_imagepath, target_path, old_uuid, new_uuid, old_thumbnail)
        self.undo_manager.push_without_execute(cmd)

        # Update the large thumbnail preview
        self.update_thumbnail_preview()

        logger.info("Thumbnail updated successfully for node %s", node_iid)




