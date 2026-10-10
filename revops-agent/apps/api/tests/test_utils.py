import base64
import logging
from uuid import uuid4

import pytest

from app.utils import oauth_state
from app.utils.crypto import CryptoError, decrypt, encrypt, generate_key
from app.utils.errors import AppError
from app.utils.idempotency import card_idempotency_key, provider_idempotency_key

K1, K2 = f"k1:{generate_key()}", f"k2:{generate_key()}"
SECRET = "xoxb-super-secret-token-123"


# ---------------------------------------------------------------- crypto
def test_encrypt_decrypt_roundtrip_and_nonce_uniqueness() -> None:
    a, b = encrypt(SECRET, keys=K1), encrypt(SECRET, keys=K1)
    assert a.key_id == "k1" and a.blob != b.blob  # random nonce
    assert decrypt(a.blob, a.key_id, keys=K1) == SECRET
    assert SECRET.encode() not in a.blob


def test_key_rotation_old_blobs_still_decrypt_new_use_first_key() -> None:
    old = encrypt(SECRET, keys=K1)
    rotated = f"{K2},{K1}"  # k2 active, k1 kept for decryption
    assert decrypt(old.blob, "k1", keys=rotated) == SECRET
    assert encrypt(SECRET, keys=rotated).key_id == "k2"
    with pytest.raises(CryptoError, match="unknown key id"):
        decrypt(old.blob, "k1", keys=K2)


def test_tamper_wrong_key_and_wrong_aad_fail_without_leaking() -> None:
    enc = encrypt(SECRET, aad=b"integration-1", keys=K1)
    for blob, kid, aad, keys in [
        (enc.blob[:-1] + bytes([enc.blob[-1] ^ 1]), "k1", b"integration-1", K1),
        (enc.blob, "k1", b"integration-2", K1),
        (enc.blob, "k1", b"integration-1", f"k1:{generate_key()}"),
    ]:
        with pytest.raises(CryptoError) as ei:
            decrypt(blob, kid, aad=aad, keys=keys)
        assert SECRET not in str(ei.value) and SECRET not in repr(ei.value)
    with pytest.raises(CryptoError):
        decrypt(b"short", "k1", keys=K1)


def test_bad_key_configuration_is_rejected() -> None:
    for spec in ("", "nokey", "k1:not-base64!!", f"k1:{base64.b64encode(b'short').decode()}"):
        with pytest.raises(CryptoError):
            encrypt("x", keys=spec)


def test_encrypted_repr_does_not_contain_plaintext(caplog: pytest.LogCaptureFixture) -> None:
    enc = encrypt(SECRET, keys=K1)
    logging.getLogger("t").warning("token stored %r", enc)
    assert SECRET not in caplog.text and SECRET not in repr(enc)


# ---------------------------------------------------------------- oauth state
async def test_state_roundtrip_binds_org_user_provider() -> None:
    org, user = uuid4(), uuid4()
    st = oauth_state.create_state(org, user, "hubspot")
    got = await oauth_state.consume_state(st, provider="hubspot")
    assert (got.org_id, got.user_id, got.provider) == (org, user, "hubspot")


async def test_state_is_single_use() -> None:
    st = oauth_state.create_state(uuid4(), uuid4(), "gmail")
    await oauth_state.consume_state(st, provider="gmail")
    with pytest.raises(AppError) as ei:
        await oauth_state.consume_state(st, provider="gmail")
    assert ei.value.code == "invalid_state" and "already used" in ei.value.message


async def test_state_rejects_tamper_wrong_provider_and_expiry() -> None:
    st = oauth_state.create_state(uuid4(), uuid4(), "hubspot")
    payload, sig = st.split(".")
    other = oauth_state.create_state(uuid4(), uuid4(), "hubspot").split(".")[0]
    for bad in (f"{other}.{sig}", f"{payload}.{sig[:-2]}xx", payload, "", "a.b", "!!!.???"):
        with pytest.raises(AppError):
            await oauth_state.consume_state(bad, provider="hubspot")
    with pytest.raises(AppError, match="different provider"):
        await oauth_state.consume_state(st, provider="slack")
    expired = oauth_state.create_state(uuid4(), uuid4(), "hubspot", ttl=-1)
    with pytest.raises(AppError, match="expired"):
        await oauth_state.consume_state(expired, provider="hubspot")


# ---------------------------------------------------------------- idempotency keys
def test_card_idempotency_key_is_stable_and_sensitive() -> None:
    org, acc, fid = uuid4(), uuid4(), uuid4()
    p1, p2 = {"a": 1, "b": [1, 2]}, {"b": [1, 2], "a": 1}
    k = card_idempotency_key(org, acc, "crm_task", fid, p1)
    assert k == card_idempotency_key(org, acc, "crm_task", fid, p2) and k.startswith("card:")
    assert k != card_idempotency_key(org, acc, "crm_task", fid, {"a": 2, "b": [1, 2]})
    assert k != card_idempotency_key(org, acc, "crm_note", fid, p1)
    assert k != card_idempotency_key(uuid4(), acc, "crm_task", fid, p1)
    assert (
        provider_idempotency_key(k)
        == provider_idempotency_key(k)
        != provider_idempotency_key(k, "2")
    )


def test_no_secret_defaults_ship_in_settings() -> None:
    from app.config import Settings

    assert Settings.model_fields["token_enc_keys"].default == ""
