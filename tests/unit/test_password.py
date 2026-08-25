from app.auth.security import hash_password, verify_password


def test_password_hashing():

    password = "secret123"

    hashed = hash_password(password)

    assert hashed != password

    assert verify_password(password, hashed)
