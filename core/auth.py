"""Kullanıcı adı/şifre doğrulama yardımcıları — sadece bu Flet sürümüne
özgü (web app/PySide6 sürümünde kullanıcı hesabı kavramı yok, o ikisi
serbest rol seçimini koruyor). Şifreler ASLA düz metin saklanmıyor: tuzlu
(salted) PBKDF2-HMAC-SHA256 kullanılıyor — Python'ın kendi `hashlib`'i
yeterli olduğu için ekstra bir bağımlılık (bcrypt vb.) eklenmedi."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """(hash, salt) çifti döner — salt verilmezse yeni bir tane üretilir
    (yeni kullanıcı/şifre değişikliği); doğrulama sırasında var olan salt
    verilir."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    if not password_hash or not salt:
        return False
    computed, _ = hash_password(password, salt)
    # Zamanlama saldırılarına karşı sabit-zamanlı karşılaştırma.
    return hmac.compare_digest(computed, password_hash)


def generate_remember_token() -> str:
    """'Beni Hatırla' için rastgele bir oturum belirteci — şifre değil,
    istenirse kullanıcının satırındaki değeri değiştirerek (ör. şifre
    sıfırlanınca) tüm cihazlardaki hatırlanan oturumlar iptal edilebilir."""
    return secrets.token_hex(24)
