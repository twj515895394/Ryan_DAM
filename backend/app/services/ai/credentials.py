from __future__ import annotations

import os
import sys
from pathlib import Path
import uuid

# Windows DPAPI support via ctypes
_HAS_WIN32 = sys.platform == "win32"
if _HAS_WIN32:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    CryptProtectData = ctypes.windll.crypt32.CryptProtectData
    CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    CryptProtectData.restype = wintypes.BOOL

    CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
    CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    CryptUnprotectData.restype = wintypes.BOOL

    LocalFree = ctypes.windll.kernel32.LocalFree
    LocalFree.argtypes = [ctypes.c_void_p]
    LocalFree.restype = ctypes.c_void_p


def _get_credentials_dir() -> Path:
    raw = os.environ.get("RYAN_DAM_DATA_DIR", str(Path.home() / ".ryan_dam" / "data"))
    data_dir = Path(raw) / "credentials"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _encrypt_bytes(data: bytes) -> bytes:
    if not _HAS_WIN32:
        # Fallback for non-windows (e.g. Linux CI test environment)
        # Obfuscate with simple XOR against a local salt
        salt = b"ryan_dam_credential_salt_v2"
        return bytes(b ^ salt[i % len(salt)] for i, b in enumerate(data))

    blob_in = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    # CRYPTPROTECT_UI_FORBIDDEN = 0x01
    if not CryptProtectData(ctypes.byref(blob_in), "Ryan_DAM", None, None, None, 1, ctypes.byref(blob_out)):
        raise RuntimeError("Windows DPAPI CryptProtectData failed")
    try:
        encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return encrypted
    finally:
        LocalFree(blob_out.pbData)


def _decrypt_bytes(encrypted: bytes) -> bytes:
    if not _HAS_WIN32:
        salt = b"ryan_dam_credential_salt_v2"
        return bytes(b ^ salt[i % len(salt)] for i, b in enumerate(encrypted))

    blob_in = DATA_BLOB(len(encrypted), ctypes.cast(ctypes.create_string_buffer(encrypted, len(encrypted)), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    # CRYPTPROTECT_UI_FORBIDDEN = 0x01
    if not CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 1, ctypes.byref(blob_out)):
        raise RuntimeError("Windows DPAPI CryptUnprotectData failed")
    try:
        decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return decrypted
    finally:
        LocalFree(blob_out.pbData)


class CredentialManager:
    """Manages encrypted storage of external service credentials on the local system."""

    @staticmethod
    def save_credential(secret: str, ref_id: str | None = None) -> str:
        """Encrypt and persist secret, returning a unique credential_ref."""
        if not ref_id:
            ref_id = f"cred_{uuid.uuid4().hex}"
        cred_file = _get_credentials_dir() / f"{ref_id}.enc"
        encrypted = _encrypt_bytes(secret.encode("utf-8"))
        cred_file.write_bytes(encrypted)
        return ref_id

    @staticmethod
    def get_credential(ref_id: str) -> str | None:
        """Decrypt and return secret, or None if not found."""
        if not ref_id:
            return None
        cred_file = _get_credentials_dir() / f"{ref_id}.enc"
        if not cred_file.exists():
            return None
        try:
            encrypted = cred_file.read_bytes()
            decrypted = _decrypt_bytes(encrypted)
            return decrypted.decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def delete_credential(ref_id: str) -> None:
        """Remove encrypted secret file."""
        if not ref_id:
            return
        cred_file = _get_credentials_dir() / f"{ref_id}.enc"
        if cred_file.exists():
            try:
                cred_file.unlink()
            except OSError:
                pass

    @staticmethod
    def mask_key(secret: str | None) -> str:
        """Return safe masked representation (e.g., 'sk-****abcd' or '****1234')."""
        if not secret:
            return ""
        s = secret.strip()
        if len(s) <= 8:
            return "****"
        return f"{s[:3]}****{s[-4:]}"
