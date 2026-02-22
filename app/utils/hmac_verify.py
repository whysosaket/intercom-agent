import hashlib
import hmac


def verify_intercom_signature(
    raw_body: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    """Verify Intercom webhook HMAC-SHA1 signature."""
    if not signature_header or not signature_header.startswith("sha1="):
        return False

    expected_sig = signature_header[5:]
    computed = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha1,
    ).hexdigest()
    return hmac.compare_digest(computed, expected_sig)
