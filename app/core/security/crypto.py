import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional


def _get_master_secret() -> bytes:
    from app.core.security.keys import SECRET_KEY
    return SECRET_KEY.encode("utf-8")


def encrypt_secret(plaintext: Optional[str]) -> str:
    """
    Encrypts a secret (e.g. AI provider API Key) with PBKDF2-HMAC-SHA256 authenticated envelope.
    Returns format 'enc:<base64-payload>'.
    """
    if not plaintext or not plaintext.strip():
        return ""
    
    clean_text = plaintext.strip()
    salt = secrets.token_bytes(16)
    master_key = _get_master_secret()
    derived_key = hashlib.pbkdf2_hmac("sha256", master_key, salt, 100000, 32)
    
    pt_bytes = clean_text.encode("utf-8")
    keystream = hashlib.sha256(derived_key + b"stream").digest()
    while len(keystream) < len(pt_bytes):
        keystream += hashlib.sha256(derived_key + keystream).digest()
        
    ciphertext = bytes(a ^ b for a, b in zip(pt_bytes, keystream[: len(pt_bytes)]))
    auth_tag = hmac.new(derived_key, salt + ciphertext, hashlib.sha256).digest()
    payload = salt + auth_tag + ciphertext
    return "enc:" + base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_secret(encrypted_text: Optional[str]) -> str:
    """
    Decrypts an authenticated secret string created by encrypt_secret.
    If the string is not prefixed with 'enc:', it returns the string as-is for backward compatibility.
    """
    if not encrypted_text:
        return ""
    if not encrypted_text.startswith("enc:"):
        return encrypted_text

    try:
        raw = base64.urlsafe_b64decode(encrypted_text[4:].encode("ascii"))
        salt = raw[:16]
        auth_tag = raw[16:48]
        ciphertext = raw[48:]
        
        master_key = _get_master_secret()
        derived_key = hashlib.pbkdf2_hmac("sha256", master_key, salt, 100000, 32)
        expected_tag = hmac.new(derived_key, salt + ciphertext, hashlib.sha256).digest()
        
        if not hmac.compare_digest(auth_tag, expected_tag):
            return ""
            
        keystream = hashlib.sha256(derived_key + b"stream").digest()
        while len(keystream) < len(ciphertext):
            keystream += hashlib.sha256(derived_key + keystream).digest()
            
        pt_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream[: len(ciphertext)]))
        return pt_bytes.decode("utf-8")
    except Exception:
        return ""
