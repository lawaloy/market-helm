"""Poisoned scrypt cost parameters must not DoS login verification."""

import time

from src.storage.users import _hash_password, _verify_password, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P


def test_verify_rejects_oversized_scrypt_n_quickly():
    """Huge N in a poisoned hash must soft-fail without calling expensive scrypt."""
    # Mint a valid shape, then inflate N far beyond what we ever write.
    stored = _hash_password("password123")
    parts = stored.split("$")
    parts[1] = str(2**20)  # 1_048_576 — would burn CPU if honored
    poisoned = "$".join(parts)

    started = time.perf_counter()
    assert _verify_password("password123", poisoned) is False
    elapsed = time.perf_counter() - started
    # Bound is generous for slow CI; real scrypt(N=2**20) is orders of magnitude slower.
    assert elapsed < 0.5


def test_verify_rejects_non_canonical_r_and_p():
    stored = _hash_password("password123")
    parts = stored.split("$")

    parts_r = list(parts)
    parts_r[2] = str(_SCRYPT_R + 1)
    assert _verify_password("password123", "$".join(parts_r)) is False

    parts_p = list(parts)
    parts_p[3] = str(_SCRYPT_P + 1)
    assert _verify_password("password123", "$".join(parts_p)) is False


def test_verify_still_accepts_canonical_hash():
    stored = _hash_password("password123")
    parts = stored.split("$")
    assert parts[1:4] == [str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P)]
    assert _verify_password("password123", stored) is True
    assert _verify_password("wrong-password", stored) is False
