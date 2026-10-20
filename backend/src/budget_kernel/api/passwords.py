"""Password hashing and policy (docs/plans/LOGIN_PLAN.md). scrypt from the standard library, so no new dependency.

Stored form: scrypt$<n>$<r>$<p>$<salt hex>$<hash hex>, so the cost can be raised later and old hashes still verify."""
from __future__ import annotations

import hashlib
import hmac
import secrets

N, R, P, DKLEN = 2**15, 8, 1, 32
MAXMEM = 128 * 1024 * 1024
MIN_LEN, MAX_LEN = 8, 128          # the upper bound stops an absurdly long input from costing more than a normal one

# The worst offenders only. A length rule plus this is a floor, not a strength guarantee.
COMMON = frozenset("""password passw0rd password1 password12 password123 password1234 12345678 123456789 1234567890 qwertyui
qwerty123 qwertyuiop iloveyou letmein1 welcome1 administrator admin1234 changeme abc12345 11111111 00000000 12341234
87654321 987654321 football baseball superman sunshine princess whatever budgetkernel passwordpassword""".split())


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=DKLEN, maxmem=MAXMEM)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${N}${R}${P}${salt.hex()}${_derive(password, salt, N, R, P).hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, want = stored.split("$")
        if scheme != "scrypt":
            return False
        got = _derive(password, bytes.fromhex(salt), int(n), int(r), int(p))
        return hmac.compare_digest(got, bytes.fromhex(want))
    except (ValueError, TypeError):
        return False


# Verified against when the username does not exist, so a missing account costs the same time as a wrong password.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def policy_problem(password: str, username: str = "") -> str | None:
    """None when acceptable, otherwise a plain sentence."""
    if len(password) < MIN_LEN:
        return f"Use at least {MIN_LEN} characters."
    if len(password) > MAX_LEN:
        return f"Use at most {MAX_LEN} characters."
    low = password.lower()
    local = username.lower().split("@")[0] if username else ""
    if low in COMMON or (len(local) >= 3 and local in low):
        return "That password is too easy to guess. Pick something else."
    return None
