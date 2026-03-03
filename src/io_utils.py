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
       
    

def export_merlin_to_zip(items, zfile):
    files_not_found = []
    logger.info("Export vers ZIP - Nombre d'items: %d", len(items))
    for item in items:
        imagepath = item['imagepath']
        if imagepath:
            filename = item['uuid'] + '.jpg'
            outfilezippath = zipfile.Path(zfile, at=filename)
            if not outfilezippath.exists():
                if imagepath[-4:] == '.jpg':
                    if os.path.exists(imagepath):
                        # Redimensionner et sauvegarder l'image avec un timestamp valide
                        with Image.open(imagepath) as image:
                            image_icon = image.resize(IMAGE_SIZE, Image.LANCZOS)
                            # Sauvegarder dans un buffer temporaire
                            img_buffer = io.BytesIO()
                            image_icon.save(img_buffer, "JPEG", mode='RGB', optimize=False, progressive=False)
                            # Créer ZipInfo avec timestamp valide
                            zip_info = zipfile.ZipInfo(filename)
                            zip_info.date_time = time.localtime(time.time())[:6]
                            zip_info.compress_type = zipfile.ZIP_DEFLATED
                            zfile.writestr(zip_info, img_buffer.getvalue())
                    else:
                        files_not_found.append(imagepath)
                else:
                    try:
                        with zipfile.ZipFile(imagepath, "r") as zin:
                            with zfile.open(filename, "w") as fout:
                                fout.write(zin.read(filename, pwd=ZIP_PASSWORD))
                    except IOError:
                        files_not_found.append(item['uuid'] + '.jpg')

        soundpath = item['soundpath']
        if soundpath:
            filename = item['uuid'] + '.mp3'
            outfilezippath = zipfile.Path(zfile, at=filename)
            if not outfilezippath.exists():
                if soundpath[-4:] == '.mp3':
                    if os.path.exists(soundpath):
                        # Créer un ZipInfo avec un timestamp valide (évite les erreurs de fichiers avec dates < 1980)
                        zip_info = zipfile.ZipInfo(filename)
                        zip_info.date_time = time.localtime(time.time())[:6]
                        zip_info.compress_type = zipfile.ZIP_DEFLATED
                        with open(soundpath, 'rb') as f:
                            zfile.writestr(zip_info, f.read())
                    else:
                        files_not_found.append(soundpath)
                else:
                    try:
                        with zipfile.ZipFile(soundpath, "r") as zin:
                            with zfile.open(filename, "w") as fout:
                                fout.write(zin.read(filename, pwd=ZIP_PASSWORD))
                    except IOError:
                        files_not_found.append(filename)

    logger.info("Écriture de playlist.bin...")
    try:
        # Créer playlist.bin dans un buffer avec timestamp valide
        playlist_buffer = io.BytesIO()
        write_merlin_playlist(playlist_buffer, items)
        # Créer ZipInfo avec timestamp valide
        zip_info = zipfile.ZipInfo("playlist.bin")
        zip_info.date_time = time.localtime(time.time())[:6]
        zip_info.compress_type = zipfile.ZIP_DEFLATED
        zfile.writestr(zip_info, playlist_buffer.getvalue())
        logger.info("playlist.bin créé avec succès")
    except Exception as e:
        logger.error("Erreur lors de la création de playlist.bin: %s", e, exc_info=True)
    
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