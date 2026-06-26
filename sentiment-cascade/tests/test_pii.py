from app import pii


def _types(entries):
    return {e.pii_type for e in entries}


def test_masks_email_phone_pan_card_account_aadhaar():
    text = (
        "Hi, I'm at rahul.k@example.com, mobile +91 9876543210, "
        "PAN ABCDE1234F, Aadhaar 1234 5678 9012, card 4111 1111 1111 1111, "
        "account 123456789012."
    )
    masked, entries = pii.mask(text)
    assert "rahul.k@example.com" not in masked
    assert "9876543210" not in masked
    assert "ABCDE1234F" not in masked
    assert "4111" not in masked
    assert {"EMAIL", "PHONE", "PAN", "AADHAAR", "CARD", "ACCOUNT"} <= _types(entries)
    assert "[EMAIL_1]" in masked and "[PAN_1]" in masked


def test_masking_is_deterministic():
    text = "Call me on 9123456789 or email a@b.com"
    out1, _ = pii.mask(text)
    out2, _ = pii.mask(text)
    assert out1 == out2


def test_no_pii_is_untouched():
    text = "The mobile app keeps crashing during fund transfers."
    masked, entries = pii.mask(text)
    assert masked == text
    assert entries == []


def test_card_not_eaten_by_account_matcher():
    # A 16-digit card must mask as CARD, not ACCOUNT.
    masked, entries = pii.mask("My card 4111111111111111 was blocked")
    assert any(e.pii_type == "CARD" for e in entries)
    assert "[CARD_1]" in masked
