from core.security import hash_password, verify_password, new_session_token, hash_token

def test_password_roundtrip():
    h = hash_password("correct horse battery")
    assert h != "correct horse battery"
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)

def test_session_token_hash_matches_and_differs_from_raw():
    raw, h = new_session_token()
    assert h == hash_token(raw) and h != raw
