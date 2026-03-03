# Technical Documentation

This document provides technical details for developers who want to understand or contribute to MerlinClaudinator.

## Architecture Overview

MerlinClaudinator is built with Python and Tkinter, following a modular architecture:

```
src/
├── merlinator.py      # Entry point
├── main_gui.py        # Main window and GUI logic
├── gui_actions.py     # GUI event handlers
├── treeviews.py       # Tree widgets for playlist/favorites
├── undo_manager.py    # Undo/redo system
├── io_utils.py        # File I/O utilities
├── image_utils.py     # Image processing
├── lazy_loader.py     # Thumbnail lazy loading with LRU cache
├── audio.py           # Audio playback widget
├── constants.py       # Configuration constants
└── icons/             # UI icons
```

---

## Hash-Based File Naming

### Why Use Hashes?

Traditional filenames can cause issues:
- Too long (> 64 bytes for Merlin)
- Special characters/accents incompatible with some systems
- Name conflicts between files

### Solution: SHA-256 in Base64

```
Source: "Histoire du Petit Chaperon Rouge.mp3"
         ↓
    [SHA-256 hash]
         ↓
    [Base64 URL-safe encoding]
         ↓
Result: "kR3tPxW9nQ2mL8vY5jZaB1cD4eF6gH7iJ8kL9mN0oP1q"
```

### Benefits
- **Unique**: Same content = same hash, different content = different hash
- **Universal**: Only uses A-Z, a-z, 0-9, -, _ (no special characters)
- **Controlled length**: Limited to 64 bytes (Merlin compatible)
- **Integrity**: Hash changes if file is modified

### Implementation

See `io_utils.py`:
```python
def generate_file_hash(filepath, max_length=64):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return base64.urlsafe_b64encode(sha256_hash.digest()).decode('ascii')[:max_length]
```

---

## Undo/Redo System

### Design Pattern

Hybrid Command pattern with two approaches:

1. **Lightweight commands** for simple operations:
   - Store only the delta (old/new values)
   - Memory: ~100-500 bytes per command
   - Used for: move, rename, toggle favorite

2. **Snapshot-based commands** for complex operations:
   - Capture complete tree state before/after
   - Memory: ~5-20 KB per command
   - Used for: drag-drop, add album, bulk operations

### Commands Implemented

| Command | Type | Description |
|---------|------|-------------|
| MoveCommand | Lightweight | Move item up/down/to parent |
| SetTitleCommand | Lightweight | Rename item |
| ToggleFavoriteCommand | Lightweight | Add/remove favorite |
| AddNodeCommand | Lightweight | Add single menu/sound |
| AddMultipleSoundsCommand | Lightweight | Add multiple sounds |
| DeleteLeafCommand | Lightweight | Delete single item |
| DeleteSubtreeCommand | Snapshot | Delete folder with children |
| SelectImageCommand | Snapshot | Change thumbnail |
| AddAlbumCommand | Snapshot | Add album folder |
| DragDropCommand | Snapshot | Drag and drop operations |

### Stack Management

- Maximum 50 operations (configurable in `constants.py`)
- Auto-cleanup when limit reached
- Stack cleared on new session/load

### Adding New Operations

```python
# In undo_manager.py
class MyCommand(Command):
    def __init__(self, gui, old_value, new_value):
        super().__init__(gui)
        self.old_value = old_value
        self.new_value = new_value
        self.description = "My Operation"

    def execute(self):
        # Apply the change
        pass

    def undo(self):
        # Reverse the change
        pass

# Usage
self.undo_manager.execute(MyCommand(self, old, new))
```

---

## Memory Optimization

### LRU Thumbnail Cache

Thumbnails are lazy-loaded and cached with LRU (Least Recently Used) eviction:

1. Thumbnails loaded on-demand when visible
2. Cache limited to 100 items (configurable)
3. Oldest thumbnails evicted when cache full
4. Evicted items reloaded when scrolled back into view

### Configuration

In `constants.py`:
```python
MAX_THUMBNAIL_CACHE_SIZE = 100  # Adjust based on memory constraints
```

### Memory Usage

| Playlist Size | Without LRU | With LRU | Savings |
|--------------|-------------|----------|---------|
| 200 items | ~150 MB | ~105 MB | ~30% |
| 500 items | ~250 MB | ~120 MB | ~52% |

---

## Drag and Drop

### Drop Zone Detection

The drag-drop system uses visual feedback to indicate drop behavior:

- **Top 25% of item**: Insert before (blue line indicator)
- **Bottom 25% of item**: Insert after (blue line indicator)
- **Center 50% of item**: Drop into folder (blue highlight)

### Implementation

In `main_gui.py`:
```python
def _get_drop_zone(self, tree, event_y, item):
    bbox = tree.bbox(item)
    relative_y = event_y - bbox[1]
    item_height = bbox[3]

    if relative_y < item_height * 0.25:
        return 'top'      # Insert before
    elif relative_y > item_height * 0.75:
        return 'bottom'   # Insert after
    else:
        return 'center'   # Drop into
```

---

## File Formats

### playlist.bin

Binary format used by Merlin device:

| Field | Size | Description |
|-------|------|-------------|
| id | 2 bytes | Item ID |
| parent_id | 2 bytes | Parent item ID |
| order | 2 bytes | Sort order |
| nb_children | 2 bytes | Number of children |
| fav_order | 2 bytes | Favorites order |
| type | 2 bytes | Item type (2=folder, 4=sound) |
| limit_time | 4 bytes | Expiration timestamp |
| add_time | 4 bytes | Add timestamp |
| uuid | 1+64 bytes | Filename (length-prefixed) |
| title | 1+66 bytes | Display title (length-prefixed) |

### Session Files (.json)

JSON format for saving work in progress:
```json
{
  "items": [...],
  "thumbnails": {...},
  "playlist_path": "..."
}
```

---

## Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| Pillow | Image processing | Yes |
| mutagen | MP3 metadata extraction | Yes |
| tkinterdnd2 | Drag-drop from file manager | Yes |
| pygame | Audio playback | Optional |

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow existing code style
4. Add appropriate undo support for new operations
5. Test with various playlist sizes
6. Submit a pull request

---

## Credits

- **Original project**: [merlinator](https://github.com/cyril-joder/merlinator) by Cyril Joder (2022)
- **Enhanced fork**: [pol51/merlinator](https://github.com/pol51/merlinator) by pol51 (2024)
- **MerlinClaudinator**: Further enhanced with Claude AI assistance (2025)
