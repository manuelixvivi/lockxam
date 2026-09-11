import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    HAS_AESGCM = True
except ImportError:
    HAS_AESGCM = False


def _get_master_secret() -> bytes:
    from app.core.security.keys import SECRET_KEY

    return SECRET_KEY.encode("utf-8")


def _derive_key(salt: bytes) -> bytes:
    master_key = _get_master_secret()
    return hashlib.pbkdf2_hmac("sha256", master_key, salt, 100000, 32)


def encrypt_secret(plaintext: Optional[str]) -> str:
    """
    Encrypts a secret (e.g. AI provider API Key) with standard AES-256-GCM AEAD envelope.
    Returns format 'enc:gcm:<base64-payload>' (or fallback PBKDF2-HMAC if AESGCM is unavailable).
    """
    if not plaintext or not plaintext.strip():
        return ""

    clean_text = plaintext.strip()
    salt = secrets.token_bytes(16)
    derived_key = _derive_key(salt)
    pt_bytes = clean_text.encode("utf-8")

    if HAS_AESGCM:
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(derived_key)
        ciphertext = aesgcm.encrypt(nonce, pt_bytes, salt)
        payload = salt + nonce + ciphertext
        return "enc:gcm:" + base64.urlsafe_b64encode(payload).decode("ascii")

    # Fallback to PBKDF2-HMAC stream cipher envelope
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
    Supports both 'enc:gcm:' (AES-256-GCM) and legacy 'enc:' (PBKDF2-HMAC envelope).
    If the string is not prefixed with 'enc:', it returns the string as-is for backward compatibility.
    """
    if not encrypted_text:
        return ""
    if not encrypted_text.startswith("enc:"):
        return encrypted_text

    # 1. Standard AES-256-GCM envelope
    if encrypted_text.startswith("enc:gcm:") and HAS_AESGCM:
        try:
            raw = base64.urlsafe_b64decode(encrypted_text[8:].encode("ascii"))
            salt = raw[:16]
            nonce = raw[16:28]
            ciphertext = raw[28:]
            derived_key = _derive_key(salt)
            aesgcm = AESGCM(derived_key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, salt)
            return decrypted.decode("utf-8")
        except Exception:
            return ""

    # 2. Legacy PBKDF2-HMAC stream cipher envelope
    try:
        raw = base64.urlsafe_b64decode(encrypted_text[4:].encode("ascii"))
        salt = raw[:16]
        auth_tag = raw[16:48]
        ciphertext = raw[48:]

        derived_key = _derive_key(salt)
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

