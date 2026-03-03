# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

import tkinter as tk
import os
import logging
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TkBase = TkinterDnD.Tk
    DND_AVAILABLE = True
    logger.info("tkinterdnd2 loaded successfully - drag-and-drop support available")
except ImportError as e:
    TkBase = tk.Tk
    DND_AVAILABLE = False
    DND_FILES = None
    logger.warning("tkinterdnd2 not available. Drag-and-drop for thumbnails will be disabled.")
    logger.warning("Install with: pip install tkinterdnd2")
    logger.debug("Import error: %s", e)

def create_tooltip(widget, text):
    """Create a simple tooltip for a widget"""
    tooltip_ref = [None]

    def on_enter(event):
        x, y, _, _ = widget.bbox("insert")
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25

        tooltip_ref[0] = tk.Toplevel(widget)
        tooltip_ref[0].wm_overrideredirect(True)
        tooltip_ref[0].wm_geometry(f"+{x}+{y}")

        label = tk.Label(tooltip_ref[0], text=text, background="#ffffe0",
                       relief='solid', borderwidth=1, font=("Arial", 9))
        label.pack()

    def on_leave(event):
        if tooltip_ref[0]:
            tooltip_ref[0].destroy()
            tooltip_ref[0] = None

    widget.bind('<Enter>', on_enter, add='+')
    widget.bind('<Leave>', on_leave, add='+')


class GUIActions(TkBase):

    def on_closing(self):
        if self.has_unsaved_changes:
            answer = tk.messagebox.askyesnocancel(
                "Quitter",
                "Vous avez des modifications non sauvegardées.\nSauvegarder avant de quitter ?"
            )
            if answer is None:  # Cancel
                return
            if answer:  # Yes - save first
                self.save_session()
        else:
            if not tk.messagebox.askokcancel("Quitter", "Voulez vous quitter MerlinClaudinator?"):
                return

        if self.sessionfile and not self.sessionfile.closed:
            self.sessionfile.close()
        if self.enable_audio and self.audio_widget.sound:
            self.audio_widget.sound.close()
        self.quit()
        self.destroy()
            
    def setTitle(self, *args):
        node = self.main_tree.selection()
        if not node:
            return

        old_title = self.main_tree.item(node, 'text')[3:]  # Remove icon prefix
        new_title = self.title_entry.get()

        if old_title == new_title:
            return

        from undo_manager import SetTitleCommand
        self.undo_manager.execute(
            SetTitleCommand(self, node, old_title, new_title)
        )

        # Hide validate button after successful validation
        self.buttonSetTitle.grid_remove()

    def sync_title_button(self, *args):
        current_string = self.title_entry.get()
        node = self.main_tree.selection()
        if node:
            original_text = self.main_tree.item(node, 'text')[3:]
            if current_string == original_text:
                # Text matches original - hide button
                self.buttonSetTitle.grid_remove()
            else:
                # Text changed - show button
                self.buttonSetTitle.grid()
            
            
            
    def sync_buttons_main(self, event=None):
        selected_node = self.main_tree.selection()

        # Always show the buttons frame
        self.move_buttons_frame.grid()

        # Edition buttons are always enabled (can always add new items)
        self.buttonAddMenu['state'] = 'normal'
        self.buttonAddAlbum['state'] = 'normal'
        self.buttonAddSound['state'] = 'normal'

        if selected_node:
            self.title_entry['state'] = "normal"
            self.buttonDelete['state'] = 'normal'

            # Hide validate button when switching to a new item
            self.buttonSetTitle.grid_remove()

            # Update move button states based on position
            index = self.main_tree.index(selected_node)
            parent = self.main_tree.parent(selected_node)
            if index>0:
                self.buttonMoveUp['state'] = 'normal'
            else:
                self.buttonMoveUp['state'] = 'disabled'
            if index == len(self.main_tree.get_children(parent))-1:
                self.buttonMoveDown['state'] = 'disabled'
            else:
                self.buttonMoveDown['state'] = 'normal'
            if parent == '':
                self.buttonMoveParentDir['state'] = 'disabled'
            else:
                self.buttonMoveParentDir['state'] = 'normal'
            if self.enable_audio:
                self.audio_widget.init()
            self.update_thumbnail_preview()  # Update thumbnail preview
        else:
            self.title_entry['state'] = "disabled"
            self.buttonDelete['state'] = 'disabled'

            # Hide validate button when nothing selected
            self.buttonSetTitle.grid_remove()

            # Disable move buttons when nothing selected
            self.buttonMoveUp['state'] = 'disabled'
            self.buttonMoveDown['state'] = 'disabled'
            self.buttonMoveParentDir['state'] = 'disabled'

            if self.enable_audio:
                self.audio_widget.init()
            self.update_thumbnail_preview()  # Clear thumbnail preview
            
            
    
    def sync_buttons_fav(self, event=None):
        selected_node = self.fav_tree.selection()

        # Always show the buttons frame
        self.fav_buttons_frame.grid()

        if selected_node:
            # Update button states based on position
            index = self.fav_tree.index(selected_node)
            if index>0:
                self.buttonMoveUpFav['state'] = 'normal'
            else:
                self.buttonMoveUpFav['state'] = 'disabled'
            if index == len(self.fav_tree.get_children(self.fav_tree.parent(selected_node)))-1:
                self.buttonMoveDownFav['state'] = 'disabled'
            else:
                self.buttonMoveDownFav['state'] = 'normal'
        else:
            # Disable buttons when nothing selected
            self.buttonMoveUpFav['state'] = 'disabled'
            self.buttonMoveDownFav['state'] = 'disabled'


    def update_thumbnail_preview(self):
        """Update the large thumbnail preview in the Contenu section"""
        selected_node = self.main_tree.selection()

        if not selected_node:
            # No selection - show placeholder
            self.thumbnail_preview_label.config(image='', text="Aucune vignette\n(Cliquer pour changer l'image)",
                                               bg='#f5f5f5', fg='#666', compound='none',
                                               width=30, height=10)
            self.current_thumbnail_photo = None
            return

        # Get the UUID for this node
        uuid = self.main_tree.set(selected_node[0], 'uuid')
        imagepath = self.main_tree.set(selected_node[0], 'imagepath')

        logger.debug("update_thumbnail_preview: uuid='%s', imagepath='%s'", uuid, imagepath)
        logger.debug("uuid in thumbnails: %s", uuid in self.thumbnails if uuid else False)
        if uuid and uuid in self.thumbnails:
            logger.debug("thumbnails[uuid] type: %s, empty: %s", type(self.thumbnails[uuid]), not self.thumbnails[uuid])

        # Check if there's a thumbnail in memory
        if uuid and uuid in self.thumbnails and self.thumbnails[uuid]:
            # Try to construct the image path if not provided
            if not imagepath or not os.path.exists(imagepath):
                # Try to construct path from playlist directory and uuid
                if self.playlistpath:
                    playlist_dir = os.path.dirname(self.playlistpath)
                    imagepath = os.path.join(playlist_dir, uuid + '.jpg')
                    logger.debug("Constructed imagepath: %s, exists: %s", imagepath, os.path.exists(imagepath))

            # Load full-size image and resize for preview
            try:
                if imagepath and os.path.exists(imagepath):
                    logger.debug("Loading image from: %s", imagepath)
                    with Image.open(imagepath) as img:
                        # Get original size
                        orig_width, orig_height = img.size
                        logger.debug("Original image size: %dx%d", orig_width, orig_height)

                        # Calculate thumbnail size maintaining aspect ratio (max 200x200)
                        img.thumbnail((200, 200), Image.LANCZOS)
                        new_width, new_height = img.size
                        logger.debug("Resized to: %dx%d", new_width, new_height)

                        # Create PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        self.current_thumbnail_photo = photo  # Keep reference

                        # Update label - remove text and show image
                        self.thumbnail_preview_label.config(image=photo, text='', bg='#f5f5f5',
                                                           compound='none', width=0, height=0)
                        logger.debug("Successfully loaded and displayed thumbnail")
                else:
                    # Image file not found
                    logger.debug("Image file not found at: %s", imagepath)
                    self.thumbnail_preview_label.config(image='', text=f"Image introuvable:\n{imagepath}\n(Cliquer pour changer)",
                                                       bg='#fff3cd', fg='#856404', compound='none',
                                                       width=30, height=10)
                    self.current_thumbnail_photo = None
            except Exception as e:
                # Error loading image
                logger.error("Error loading image: %s", e)
                self.thumbnail_preview_label.config(image='', text=f"Erreur: {str(e)}\n(Cliquer pour changer)",
                                                   bg='#f8d7da', fg='#721c24', compound='none',
                                                   width=30, height=10)
                self.current_thumbnail_photo = None
        else:
            # No thumbnail available
            logger.debug("No thumbnail in memory for uuid: %s", uuid)
            node_type = "menu" if self.main_tree.tag_has('directory', selected_node[0]) else "son"
            self.thumbnail_preview_label.config(image='', text=f"Aucune vignette pour ce {node_type}\n(Cliquer pour en ajouter une)",
                                               bg='#f5f5f5', fg='#666', compound='none',
                                               width=30, height=10)
            self.current_thumbnail_photo = None



    def synchronise_selection(self, event):
        w = event.widget
        if w == self.main_tree:
            selected_node = w.selection()
            if selected_node and self.fav_tree.exists(selected_node):
                if self.fav_tree.selection() != selected_node:
                    self.fav_tree.selection_set(selected_node)
                    self.fav_tree.see(selected_node)
            else:
                if self.fav_tree.selection():
                    self.fav_tree.selection_set([])
            self.title_entry.delete(0, 'end')
            self.title_entry.insert(0, self.main_tree.item(self.main_tree.selection(),'text')[3:])
            self.sync_buttons_main()
            
        elif w == self.fav_tree:
            selected_node = w.selection()
            if selected_node and self.main_tree.selection() != selected_node:
                    self.main_tree.selection_set(selected_node)
                    self.main_tree.see(selected_node)
            self.sync_buttons_fav()
        else:
            return
        

class TwoButtonCancelDialog(tk.simpledialog.Dialog):
    def __init__(self, parent, title, prompt, button0text, button1text):
        self.res = 2
        self.prompt = prompt
        self.button0text = button0text
        self.button1text = button1text
        super().__init__(parent, title)
        
    def body(self, frame):
        self.label = tk.Label(frame, width=40, text=self.prompt)
        self.label.pack()
        return frame
        
    def button_pressed(self, button):
        self.res = button
        self.destroy()


    def buttonbox(self):
        self.button0 = tk.Button(self, text=self.button0text, width=12, command=lambda:self.button_pressed(0))
        self.button0.focus_set()
        self.button0.focus()
        self.button0.pack(fill=tk.NONE, expand=True, side=tk.LEFT)
        self.button1 = tk.Button(self, text=self.button1text, width=12, command=lambda:self.button_pressed(1))
        self.button1.pack(fill=tk.NONE, expand=True, side=tk.LEFT)
        self.cancel_button = tk.Button(self, text='Annuler', width=12, command=lambda:self.button_pressed(2))
        self.cancel_button.pack(fill= tk.NONE, expand=True, side=tk.RIGHT)
        self.bind("<Escape>", lambda event: self.button_pressed(2))
        self.bind("<Return>", lambda event: self.focus_get().invoke() if hasattr(self.focus_get(), 'invoke') else None)
        
       
