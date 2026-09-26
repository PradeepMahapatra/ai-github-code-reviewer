import hashlib
import hmac

from pydantic import SecretStr


def is_valid_signature(
    payload: bytes,
    received_signature: str | None,
    secret: SecretStr | None,
) -> bool:
    if (
        secret is None
        or not secret.get_secret_value()
        or received_signature is None
    ):
        return False
    if not received_signature.startswith("sha256="):
        return False

    signature = received_signature.removeprefix("sha256=")
    if len(signature) != hashlib.sha256().digest_size * 2:
        return False
    try:
        signature_bytes = bytes.fromhex(signature)
    except ValueError:
        return False

    expected_signature = hmac.new(
        secret.get_secret_value().encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()
    return hmac.compare_digest(signature_bytes, expected_signature)
