from app.auth.jwt_handler import create_access_token


def test_create_access_token():

    token = create_access_token({"sub": "1"})

    assert isinstance(token, str)

    assert len(token) > 0


def test_token_contains_three_parts():

    token = create_access_token({"sub": "1"})

    parts = token.split(".")

    assert len(parts) == 3


def test_multiple_tokens_created():

    token1 = create_access_token({"sub": "1"})

    token2 = create_access_token({"sub": "2"})

    assert token1 != token2
