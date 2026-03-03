# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.

"""
Audio playback widget with play/pause controls and progress slider.
"""
import time
import tkinter as tk
from tkinter import ttk
import zipfile
import logging
from pathlib import Path
from PIL import Image, ImageTk, ImageEnhance
from constants import get_src_path

logger = logging.getLogger(__name__)

# Import pygame and mutagen in a try-except block
# to allow the app to run without audio support if these libraries fail
try:
    from pygame import mixer
    from mutagen.mp3 import MP3
    AUDIO_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    AUDIO_AVAILABLE = False
    logger.warning("Audio support disabled: %s", e)
    # Raise the exception at module level to prevent AudioWidget import
    raise ImportError("Audio libraries (pygame/mutagen) not available") from e

class AudioWidget(tk.Frame):
    """
    Audio player widget with playback controls.

    Features:
    - Play/Pause button with visual feedback
    - Progress slider with seek capability
    - Time display (current/total)
    - Support for both file and ZIP-based MP3 playback
    """

    def __init__(self, parent, root=None, **kwargs):
        tk.Frame.__init__(self, parent, **kwargs)
        if root is None:
            self.rootGUI = parent
        else:
            self.rootGUI = root
        mixer.init()
        self.sound = None
        self.soundpath = None  # Store path to reopen file if needed
        self.sound_from_zip = False  # Track if sound is from zip
        self.sound_zip_filename = None  # Filename within zip
        self.zipfile_handle = None  # Keep zipfile open for zip sounds
        self.start_time = 0
        self.pause_time = 0
        self.sound_length = 0
        self.looping = False
        self.playing = False
        self.pending_seek_position = 0  # Position to start from when Play is first called

        # Load icon images
        self._load_icons()

        # Configure grid layout (3 columns in a single row)
        self.grid_rowconfigure(0, weight=1)  # Center row vertically
        self.grid_columnconfigure(0, weight=0)  # Play button column (fixed width)
        self.grid_columnconfigure(1, weight=1)  # Slider column (expandable)
        self.grid_columnconfigure(2, weight=0)  # Time label column (fixed width)

        # Play/Pause button with dynamic icon (left side)
        # Get parent background color for transparency effect
        parent_bg = self.cget('background')
        hover_bg = '#e5e5e5'  # Darker grey for hover/active state

        if self.use_image_icons:
            self.play_button = tk.Button(self, image=self.play_icon,
                                         command=self.PlayPause, state='disabled',
                                         relief='flat', bd=0, bg=parent_bg,
                                         activebackground=hover_bg,
                                         highlightthickness=0)
        else:
            # Fallback to text icons (width reduced from 4 to 2)
            self.play_button = tk.Button(self, text="▶", font=("Arial", 14), width=2,
                                         command=self.PlayPause, state='disabled',
                                         relief='flat', bd=0, bg=parent_bg,
                                         fg='#666666', activebackground=hover_bg,
                                         activeforeground='#444444',
                                         highlightthickness=0)
        self.play_button.grid(row=0, column=0, padx=(0, 8), pady=(0, 10), sticky='nsw')

        # Add hover effect - darken background on mouse enter
        self._setup_button_hover_effect()

        self.create_tooltip(self.play_button, "Play/Pause (Espace)")

        # Progress bar (column 1) - centered vertically
        self.progress_canvas = tk.Canvas(self, height=8, bg='#999999',
                                        highlightthickness=0, bd=0)
        self.progress_canvas.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=(0, 10))

        # White fill rectangle that grows
        self.progress_fill = self.progress_canvas.create_rectangle(0, 0, 0, 8,
                                                                   fill='white', outline='')

        # Bind mouse events for scrubbing
        self.progress_canvas.bind('<Button-1>', self.on_progress_click)
        self.progress_canvas.bind('<B1-Motion>', self.on_progress_drag)
        self.progress_canvas.bind('<ButtonRelease-1>', self.on_progress_release)
        self.progress_canvas.bind('<Configure>', self.on_progress_resize)

        # Track dragging state
        self.is_dragging = False
        self.was_playing_before_drag = False

        # Time display label (right side)
        self.slider_label = tk.Label(self, text="00:00 / 00:00", font=("Arial", 10))
        self.slider_label.grid(row=0, column=2, sticky='e', pady=(0, 10))

    def _load_icons(self):
        """Load play and pause icon images from src directory."""
        try:
            icons_dir = get_src_path('icons')
            play_icon_path = icons_dir / 'play_icon.png'
            pause_icon_path = icons_dir / 'pause_icon.png'

            # Load images
            play_img = Image.open(play_icon_path).convert('RGBA')
            pause_img = Image.open(pause_icon_path).convert('RGBA')

            # Scale down images to 40% of original size (divide by 2.5)
            scale_factor = 0.4  # 1/2.5 = 0.4
            play_size = (int(play_img.width * scale_factor), int(play_img.height * scale_factor))
            pause_size = (int(pause_img.width * scale_factor), int(pause_img.height * scale_factor))

            play_img = play_img.resize(play_size, Image.LANCZOS)
            pause_img = pause_img.resize(pause_size, Image.LANCZOS)

            # Darken images to 0.15 brightness (15% of original brightness)
            brightness_factor = 0.15
            play_enhancer = ImageEnhance.Brightness(play_img)
            pause_enhancer = ImageEnhance.Brightness(pause_img)

            play_img = play_enhancer.enhance(brightness_factor)
            pause_img = pause_enhancer.enhance(brightness_factor)

            # Create PhotoImage objects
            self.play_icon = ImageTk.PhotoImage(play_img)
            self.pause_icon = ImageTk.PhotoImage(pause_img)
            self.use_image_icons = True

            logger.debug("Loaded play and pause icons successfully (scaled to %s%%, brightness %s%%)", scale_factor*100, brightness_factor*100)
        except Exception as e:
            logger.error("Failed to load icon images: %s", e)
            # Fallback to text-based icons if images fail to load
            logger.warning("Using text-based fallback icons")
            self.play_icon = None
            self.pause_icon = None
            self.use_image_icons = False

    def update_progress_bar(self, current_time):
        """Update the white fill based on current playback position."""
        if self.sound_length > 0:
            canvas_width = self.progress_canvas.winfo_width()
            if canvas_width > 1:
                progress_ratio = min(current_time / self.sound_length, 1.0)
                fill_width = int(canvas_width * progress_ratio)
                self.progress_canvas.coords(self.progress_fill, 0, 0, fill_width, 8)

    def on_progress_resize(self, event=None):
        """Handle canvas resize - redraw progress fill."""
        if self.start_time:
            if self.pause_time:
                current_time = self.pause_time - self.start_time
            else:
                current_time = time.time() - self.start_time
            self.update_progress_bar(current_time)
        else:
            self.update_progress_bar(0)

    def on_progress_click(self, event):
        """Handle click on progress bar - start seeking."""
        if not self.sound_length:
            return

        # Remember playback state before scrubbing
        self.was_playing_before_drag = self.start_time and not self.pause_time
        self.had_started_before_drag = self.start_time != 0  # Track if music had ever started
        if self.was_playing_before_drag:
            self.Pause()

        self.is_dragging = True

        # Calculate position
        canvas_width = self.progress_canvas.winfo_width()
        click_ratio = max(0, min(1, event.x / canvas_width))
        new_position = click_ratio * self.sound_length

        # Update display
        self.update_progress_bar(new_position)
        elapsed_time = time.strftime("%M:%S", time.gmtime(new_position))
        total_time = time.strftime("%M:%S", time.gmtime(self.sound_length))
        self.slider_label.config(text=f"{elapsed_time} / {total_time}")

    def on_progress_drag(self, event):
        """Handle dragging on progress bar - continuous seeking."""
        if not self.sound_length or not self.is_dragging:
            return

        # Calculate position
        canvas_width = self.progress_canvas.winfo_width()
        click_ratio = max(0, min(1, event.x / canvas_width))
        new_position = click_ratio * self.sound_length

        # Update display only (playback updated on release)
        self.update_progress_bar(new_position)
        elapsed_time = time.strftime("%M:%S", time.gmtime(new_position))
        total_time = time.strftime("%M:%S", time.gmtime(self.sound_length))
        self.slider_label.config(text=f"{elapsed_time} / {total_time}")

    def on_progress_release(self, event):
        """Handle mouse release - complete the seek operation."""
        if not self.sound_length or not self.is_dragging:
            return

        self.is_dragging = False

        # Calculate final position
        canvas_width = self.progress_canvas.winfo_width()
        click_ratio = max(0, min(1, event.x / canvas_width))
        new_position = click_ratio * self.sound_length

        # Handle different states
        if not self.had_started_before_drag:
            # Music never started - just store seek position for when Play is called
            self.pending_seek_position = new_position
            # Don't modify start_time/pause_time - leave them at 0
        elif self.was_playing_before_drag:
            # Was playing - resume from new position
            self.start_time = time.time() - new_position
            self.pause_time = 0  # Reset pause state since we're playing again
            mixer.music.play(start=new_position)
            self._set_button_icon(is_playing=True)  # Restore pause icon since still playing
        else:
            # Was paused - update position but stay paused
            self.start_time = time.time() - new_position
            self.pause_time = time.time()

        # Update display
        self.update_progress_bar(new_position)
        elapsed_time = time.strftime("%M:%S", time.gmtime(new_position))
        total_time = time.strftime("%M:%S", time.gmtime(self.sound_length))
        self.slider_label.config(text=f"{elapsed_time} / {total_time}")

    def _set_button_icon(self, is_playing):
        """Set the play/pause button icon based on playback state.

        Args:
            is_playing: True for pause icon (currently playing), False for play icon
        """
        if self.use_image_icons:
            icon = self.pause_icon if is_playing else self.play_icon
            self.play_button.config(image=icon)
        else:
            text = "‖" if is_playing else "▶"
            self.play_button.config(text=text)

    def _setup_button_hover_effect(self):
        """Setup hover effect for play button - darken background on hover."""
        # Store original background color
        self.button_normal_bg = self.play_button.cget('background')

        # Create slightly darker background for hover (20% darker)
        self.button_hover_bg = '#e5e5e5'  # Slightly darker grey for hover effect

        def on_enter(event):
            if self.play_button['state'] != 'disabled':
                self.play_button.config(bg=self.button_hover_bg)

        def on_leave(event):
            self.play_button.config(bg=self.button_normal_bg)

        # Use add='+' to allow multiple bindings to the same event
        self.play_button.bind('<Enter>', on_enter, add='+')
        self.play_button.bind('<Leave>', on_leave, add='+')

    def create_tooltip(self, widget, text):
        """Create a simple tooltip for a widget. Delegates to shared implementation."""
        from gui_actions import create_tooltip
        create_tooltip(widget, text)

    def update_play_time(self):
        """Update the time display and progress bar during playback."""
        total_time = time.strftime("%M:%S", time.gmtime(self.sound_length))
        if self.start_time:
            if self.pause_time:
                current_time = self.pause_time - self.start_time
            else:
                current_time = time.time() - self.start_time
        elif self.pending_seek_position:
            # Music hasn't started but user scrubbed to a position
            current_time = self.pending_seek_position
        else:
            current_time = 0
        elapsed_time = time.strftime("%M:%S", time.gmtime(current_time))
        self.slider_label.config(text=f"{elapsed_time} / {total_time}")

        # Update the visual progress fill
        self.update_progress_bar(current_time)

        self.after(200, self.update_play_time)
            

    def init(self):
        """Initialize audio player with the currently selected sound from the tree."""
        main_tree = self.rootGUI.main_tree
        selected_node = main_tree.selection()
        self.Stop()

        # Properly close existing file handles
        if self.sound:
            try:
                self.sound.close()
            except (OSError, ValueError) as e:
                logger.debug("Error closing sound file: %s", e)
        if self.zipfile_handle:
            try:
                self.zipfile_handle.close()
            except (OSError, ValueError) as e:
                logger.debug("Error closing zipfile: %s", e)

        self.start_time = 0
        self.pause_time = 0
        self.pending_seek_position = 0
        self.sound = None
        self.soundpath = None
        self.sound_from_zip = False
        self.sound_zip_filename = None
        self.zipfile_handle = None
        self.sound_length = 0

        if selected_node and main_tree.tag_has('sound', selected_node) and main_tree.set(selected_node, 'soundpath'):
            soundpath = main_tree.set(selected_node, 'soundpath')
            self.soundpath = soundpath

            if soundpath[-4:] == '.zip':
                filename = main_tree.set(selected_node, 'uuid') + '.mp3'
                self.sound_from_zip = True
                self.sound_zip_filename = filename
                # Keep zipfile open for reuse
                self.zipfile_handle = zipfile.ZipFile(soundpath, 'r')
                zippath = zipfile.Path(self.zipfile_handle, at=filename)
                if zippath.exists():
                    # Use single file handle for MP3 analysis and playback
                    with self.zipfile_handle.open(filename, 'r') as temp_sound:
                        sound_mut = MP3(temp_sound)
                        self.sound_length = sound_mut.info.length
                    # Open fresh handle for playback
                    self.sound = self.zipfile_handle.open(filename, 'r')
            else:
                self.sound_from_zip = False
                # Use single file handle for MP3 analysis and playback
                with open(soundpath, 'rb') as temp_sound:
                    sound_mut = MP3(temp_sound)
                    self.sound_length = sound_mut.info.length
                # Open fresh handle for playback
                self.sound = open(soundpath, 'rb')

            self.play_button['state'] = 'normal'
        else:
            self.play_button['state'] = 'disabled'

        # Reset visual progress fill
        self.update_progress_bar(0)
        self._set_button_icon(is_playing=False)  # Reset to play icon
        if not self.looping:
                self.update_play_time()
                self.looping = True


    def Play(self):
        """Start or resume audio playback."""
        if self.soundpath:
            try:
                # Reopen the file if needed (e.g., after Stop)
                need_reopen = False
                try:
                    # Check if file is closed
                    if self.sound is None:
                        need_reopen = True
                    elif hasattr(self.sound, 'closed') and self.sound.closed:
                        need_reopen = True
                    else:
                        # Try to read current position - if it fails, need to reopen
                        try:
                            pos = self.sound.tell()
                        except (ValueError, OSError):
                            need_reopen = True
                except (AttributeError, ValueError):
                    need_reopen = True

                logger.debug("Play: need_reopen=%s, sound_from_zip=%s", need_reopen, self.sound_from_zip)

                if need_reopen:
                    if self.sound_from_zip:
                        # Reopen from zip using the kept zipfile handle
                        if self.zipfile_handle:
                            logger.debug("Reopening from zip: %s", self.sound_zip_filename)
                            self.sound = self.zipfile_handle.open(self.sound_zip_filename, 'r')
                        else:
                            logger.error("Zipfile handle is None!")
                            return
                    else:
                        # Reopen regular file
                        logger.debug("Reopening regular file: %s", self.soundpath)
                        self.sound = open(self.soundpath, 'rb')

                # Seek to beginning
                try:
                    self.sound.seek(0)
                    logger.debug("Seeked to beginning")
                except Exception as e:
                    logger.debug("Could not seek: %s", e)

                logger.debug("Loading sound into mixer...")
                mixer.music.load(self.sound)
                logger.debug("Starting playback...")
                self.pause_time = 0

                # Check if there's a pending seek position from scrubbing before play
                start_position = self.pending_seek_position
                self.pending_seek_position = 0  # Reset pending seek

                self.start_time = time.time() - start_position
                mixer.music.play(start=start_position)
                self._set_button_icon(is_playing=True)  # Change to pause icon
                logger.debug("Play completed successfully at position %.2f", start_position)
            except Exception as e:
                logger.error("Play failed: %s: %s", type(e).__name__, e, exc_info=True)

    def Pause(self):
        """Pause audio playback."""
        self.pause_time = time.time()
        mixer.music.pause()
        self._set_button_icon(is_playing=False)  # Change to play icon
    
    def Stop(self):
        """Internal method to stop playback and reset state."""
        logger.debug("Stop called")
        mixer.music.stop()
        mixer.music.unload()  # Unload from mixer to allow clean reload
        if self.start_time:
            self.start_time = 0
            self.pause_time = 0
        # Keep file handle open but reset it for next Play
        if self.sound:
            try:
                self.sound.seek(0)
                logger.debug("Reset file position to beginning")
            except Exception as e:
                logger.debug("Could not reset file position: %s", e)
        # Reset visual progress fill
        self.update_progress_bar(0)
        self._set_button_icon(is_playing=False)  # Change to play icon
        logger.debug("Stop completed")

    def Resume(self):
        """Resume audio playback after pause."""
        delta = time.time() - self.pause_time
        self.pause_time = 0
        self.start_time += delta
        mixer.music.unpause()
        self._set_button_icon(is_playing=True)  # Change to pause icon

    def PlayPause(self, event=None):
        """Toggle between play and pause states."""
        if self.start_time:
            if self.pause_time:
                self.Resume()
            else:
                self.Pause()
        else:
            self.Play()

    def cleanup(self):
        """Cleanup all resources - call this before destroying the widget"""
        self.Stop()
        if self.sound:
            try:
                self.sound.close()
            except (OSError, ValueError) as e:
                logger.debug("Error closing sound in cleanup: %s", e)
        if self.zipfile_handle:
            try:
                self.zipfile_handle.close()
            except (OSError, ValueError) as e:
                logger.debug("Error closing zipfile in cleanup: %s", e)
        self.sound = None
        self.zipfile_handle = None

    def destroy(self):
        """Override destroy to ensure cleanup"""
        self.cleanup()
        super().destroy()
