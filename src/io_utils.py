# Copyright 2022 by Cyril Joder.
# All rights reserved.
# This file is part of MerlinClaudinator (based on merlinator), and is released under the
# "MIT License Agreement". Please see the LICENSE file
# that should have been included as part of this package.


from PIL import Image
from PIL.ImageTk import PhotoImage
import zipfile
import os.path
import json
import struct
import io
import hashlib
import base64
import time
import logging

logger = logging.getLogger(__name__)

# Import mutagen for MP3 metadata extraction
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

from constants import *

bytezero = b'\x00'


def read_merlin_playlist(stream):

    items = []
    while (b:=stream.read(2)):
        
        item = dict()
        # id
        if not b: raise Exception("wrong file format")
        item['id'] = int.from_bytes(b, byteorder='little')
        
        # id du parent
        b = stream.read(2)
        if not b: raise Exception("wrong file format")
        item['parent_id'] = int.from_bytes(b, byteorder='little')
        
        # ordre
        b = stream.read(2)
        if not b: raise Exception("wrong file format")
        item['order'] = int.from_bytes(b, byteorder='little')
        
        # nb_enfants
        b = stream.read(2)
        if not b: raise Exception("wrong file format")
        item['nb_children'] = int.from_bytes(b, byteorder='little')
        
        # ordre dans les favoris
        b = stream.read(2)
        if not b: raise Exception("wrong file format")
        item['fav_order'] = int.from_bytes(b, byteorder='little')
        
        # type d'item
        b = stream.read(2)
        if not b: raise Exception("wrong file format")
        item['type'] = int.from_bytes(b, byteorder='little')
        
        # date limite
        b = stream.read(4)
        if not b: raise Exception("wrong file format")
        item['limit_time'] = int.from_bytes(b, byteorder='little')
        
        # date d'ajout
        b = stream.read(4)
        if not b: raise Exception("wrong file format")
        item['add_time'] = int.from_bytes(b, byteorder='little')
        
        # uuid (nom de fichier)
        b = stream.read(1)
        if not b: raise Exception("wrong file format")
        length = int.from_bytes(b, byteorder='little')
        b = stream.read(length)
        item['uuid'] = b.decode('UTF-8')
        b = stream.read(MAX_FILENAME_LENGTH - length)

        # titre
        b = stream.read(1)
        if not b: raise Exception("wrong file format")
        length = int.from_bytes(b, byteorder='little')
        b = stream.read(length)
        item['title'] = b.decode('UTF-8')
        b = stream.read(MAX_TITLE_LENGTH - length)
        
        items.append(item)
    return items



def write_merlin_playlist(stream, items):
    
    for item in items:

        # id
        b = item['id'].to_bytes(2,byteorder='little')
        stream.write(b)
        
        # id du parent
        b = item['parent_id'].to_bytes(2, byteorder='little')
        stream.write(b)
        
        # ordre
        b = item['order'].to_bytes(2, byteorder='little')
        stream.write(b)
        
        # nb_enfants
        b = item['nb_children'].to_bytes(2, byteorder='little')
        stream.write(b)
        
        # ordre dans les favoris
        b = item['fav_order'].to_bytes(2, byteorder='little')
        stream.write(b)
        
        # type d'item
        b = item['type'].to_bytes(2, byteorder='little')
        stream.write(b)
        
        # date limite
        b = item['limit_time'].to_bytes(4, byteorder='little')
        stream.write(b)
        
        # date d'ajout
        b = item['add_time'].to_bytes(4, byteorder='little')
        stream.write(b)
        
        # uuid (nom de fichier)
        b = item['uuid'].encode('UTF-8')
        length = len(b)
        length_b = length.to_bytes(1, byteorder='little')
        stream.write(length_b)
        stream.write(b)
        stream.write(bytezero * (MAX_FILENAME_LENGTH - length))

        # titre
        b = item['title'].encode('UTF-8')
        length = len(b)
        length_b = length.to_bytes(1, byteorder='little')
        stream.write(length_b)
        stream.write(b)
        stream.write(bytezero * (MAX_TITLE_LENGTH - length))
    
def format_item(item):
    for key in ("fav_order", "type", "limit_time", "add_time", "nb_children"):
        if type(item[key]) is not int:
            if item[key]:
                item[key] = int(item[key])
            else:
                item[key] = 0
    return item
       
    

def export_merlin_to_zip(items, zfile, progress_callback=None):
    """
    Export items to a ZIP file.

    Args:
        items: List of items to export
        zfile: ZipFile object opened in write mode
        progress_callback: Optional callback function(current, total, message) for progress updates

    Returns:
        List of files that were not found
    """
    files_not_found = []
    written_files = set()  # Track files already written to avoid duplicates
    total_items = len(items)
    logger.info("Export vers ZIP - Nombre d'items: %d", total_items)

    for idx, item in enumerate(items):
        # Update progress
        if progress_callback:
            title = item.get('title', item.get('uuid', ''))[:30]
            progress_callback(idx, total_items, f"Export: {title}")

        # Export image
        imagepath = item.get('imagepath', '')
        if imagepath:
            filename = item['uuid'] + '.jpg'
            if filename not in written_files:
                try:
                    if imagepath.lower().endswith('.jpg') or imagepath.lower().endswith('.jpeg'):
                        if os.path.exists(imagepath):
                            logger.debug("Exporting image: %s -> %s", imagepath, filename)
                            with Image.open(imagepath) as image:
                                # Convert to RGB if necessary (handles RGBA, P, etc.)
                                if image.mode != 'RGB':
                                    image = image.convert('RGB')
                                image_icon = image.resize(IMAGE_SIZE, Image.LANCZOS)
                                img_buffer = io.BytesIO()
                                image_icon.save(img_buffer, "JPEG", quality=85, optimize=False, progressive=False)
                                zip_info = zipfile.ZipInfo(filename)
                                zip_info.date_time = time.localtime(time.time())[:6]
                                zip_info.compress_type = zipfile.ZIP_DEFLATED
                                zfile.writestr(zip_info, img_buffer.getvalue())
                                written_files.add(filename)
                        else:
                            logger.warning("Image file not found: %s", imagepath)
                            files_not_found.append(imagepath)
                    elif imagepath.lower().endswith('.zip'):
                        # Read from ZIP archive
                        try:
                            with zipfile.ZipFile(imagepath, "r") as zin:
                                data = zin.read(filename, pwd=ZIP_PASSWORD)
                                zip_info = zipfile.ZipInfo(filename)
                                zip_info.date_time = time.localtime(time.time())[:6]
                                zip_info.compress_type = zipfile.ZIP_DEFLATED
                                zfile.writestr(zip_info, data)
                                written_files.add(filename)
                        except (IOError, KeyError, zipfile.BadZipFile) as e:
                            logger.warning("Failed to read image from ZIP %s: %s", imagepath, e)
                            files_not_found.append(item['uuid'] + '.jpg')
                    else:
                        logger.warning("Unsupported image format: %s", imagepath)
                        files_not_found.append(imagepath)
                except Exception as e:
                    logger.error("Error exporting image %s: %s", imagepath, e, exc_info=True)
                    files_not_found.append(imagepath)

        # Export sound
        soundpath = item.get('soundpath', '')
        if soundpath:
            filename = item['uuid'] + '.mp3'
            if filename not in written_files:
                try:
                    if soundpath.lower().endswith('.mp3'):
                        if os.path.exists(soundpath):
                            logger.debug("Exporting sound: %s -> %s", soundpath, filename)
                            zip_info = zipfile.ZipInfo(filename)
                            zip_info.date_time = time.localtime(time.time())[:6]
                            zip_info.compress_type = zipfile.ZIP_DEFLATED
                            with open(soundpath, 'rb') as f:
                                zfile.writestr(zip_info, f.read())
                            written_files.add(filename)
                        else:
                            logger.warning("Sound file not found: %s", soundpath)
                            files_not_found.append(soundpath)
                    elif soundpath.lower().endswith('.zip'):
                        # Read from ZIP archive
                        try:
                            with zipfile.ZipFile(soundpath, "r") as zin:
                                data = zin.read(filename, pwd=ZIP_PASSWORD)
                                zip_info = zipfile.ZipInfo(filename)
                                zip_info.date_time = time.localtime(time.time())[:6]
                                zip_info.compress_type = zipfile.ZIP_DEFLATED
                                zfile.writestr(zip_info, data)
                                written_files.add(filename)
                        except (IOError, KeyError, zipfile.BadZipFile) as e:
                            logger.warning("Failed to read sound from ZIP %s: %s", soundpath, e)
                            files_not_found.append(filename)
                    else:
                        logger.warning("Unsupported sound format: %s", soundpath)
                        files_not_found.append(soundpath)
                except Exception as e:
                    logger.error("Error exporting sound %s: %s", soundpath, e, exc_info=True)
                    files_not_found.append(soundpath)

    # Write playlist.bin
    logger.info("Écriture de playlist.bin...")
    if progress_callback:
        progress_callback(total_items, total_items, "Création de playlist.bin...")

    try:
        playlist_buffer = io.BytesIO()
        write_merlin_playlist(playlist_buffer, items)
        zip_info = zipfile.ZipInfo("playlist.bin")
        zip_info.date_time = time.localtime(time.time())[:6]
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        zfile.writestr(zip_info, playlist_buffer.getvalue())
        written_files.add("playlist.bin")
        logger.info("playlist.bin créé avec succès (%d bytes)", len(playlist_buffer.getvalue()))
    except Exception as e:
        logger.error("Erreur lors de la création de playlist.bin: %s", e, exc_info=True)
        raise  # Re-raise to notify caller

    if progress_callback:
        progress_callback(total_items, total_items, "Export terminé!")

    logger.info("Export terminé - %d fichiers écrits, %d fichiers non trouvés", len(written_files), len(files_not_found))
    return files_not_found
        

def IsImageProgressive(stream):
    #with open(filename, "rb") as stream:
    while True:
        blockStart = struct.unpack('B', stream.read(1))[0]
        if blockStart != 0xff:
            raise ValueError(f'Invalid char code {blockStart} - not a JPEG file')

        blockType = struct.unpack('B', stream.read(1))[0]
        if blockType == 0xd8:   # Start Of Image
            continue
        elif blockType == 0xc0: # Start of baseline frame
            return False
        elif blockType == 0xc2: # Start of progressive frame
            return True
        elif blockType >= 0xd0 and blockType <= 0xd7: # Restart
            continue
        elif blockType == 0xd9: # End Of Image
            break
        else:                   # Variable-size block, just skip it
            blockSize = struct.unpack('2B', stream.read(2))
            blockSize = blockSize[0] * 256 + blockSize[1] - 2
            stream.seek(blockSize, 1)
    return False


def generate_file_hash(filepath, max_length=MAX_FILENAME_LENGTH):
    """
    Génère un hash unique en base64 pour un fichier, compatible avec les systèmes de fichiers.

    Args:
        filepath: Chemin vers le fichier
        max_length: Longueur maximale du hash (MAX_FILENAME_LENGTH octets pour Merlin)
        
    Returns:
        String hash en base64 (sans caractères problématiques)
    """
    # Calculer le hash SHA256 du fichier
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Lire le fichier par chunks pour gérer les gros fichiers
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    # Encoder en base64 et rendre compatible filesystem
    hash_bytes = sha256_hash.digest()
    hash_b64 = base64.urlsafe_b64encode(hash_bytes).decode('ascii')
    
    # Retirer les caractères de padding et limiter la longueur
    hash_b64 = hash_b64.rstrip('=')
    
    # Limiter à max_length octets (compatibilité Merlin)
    if len(hash_b64) > max_length:
        hash_b64 = hash_b64[:max_length]
    
    return hash_b64


def extract_and_resize_mp3_thumbnail(mp3_filepath, output_image_path):
    """
    Extrait la vignette (album art) d'un fichier MP3, la redimensionne à 128x128
    et la sauvegarde au format JPEG non-progressif.
    
    Args:
        mp3_filepath: Chemin vers le fichier MP3
        output_image_path: Chemin de sortie pour l'image JPG
        
    Returns:
        True si l'extraction a réussi, False sinon
    """
    if not MUTAGEN_AVAILABLE:
        return False
    
    try:
        # Charger le fichier MP3
        audio = MP3(mp3_filepath, ID3=ID3)
        
        # Rechercher les tags d'image (APIC = Attached Picture)
        if audio.tags is None:
            return False
            
        # Chercher la pochette d'album
        image_data = None
        for tag in audio.tags.values():
            if isinstance(tag, APIC):
                image_data = tag.data
                break
        
        if image_data is None:
            return False
        
        # Charger l'image depuis les données binaires
        image_stream = io.BytesIO(image_data)
        image = Image.open(image_stream)
        
        # Convertir en RGB si nécessaire (pour éviter les problèmes avec RGBA ou autres modes)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        
        # Redimensionner à IMAGE_SIZE
        image_resized = image.resize(IMAGE_SIZE, Image.LANCZOS)
        
        # Sauvegarder au format JPEG baseline (non-progressif)
        image_resized.save(output_image_path, 'JPEG', quality=85, optimize=False, progressive=False)
        
        return True

    except Exception as e:
        logger.error("Erreur lors de l'extraction de la vignette: %s", e)
        return False