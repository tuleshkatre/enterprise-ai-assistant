from app.db.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db):
        self.db = db

    def create(self, refresh_token):
        self.db.add(refresh_token)
        self.db.commit()
        self.db.refresh(refresh_token)

        return refresh_token

    def get_by_token(self, token: str):
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.refresh_token == token)
            .first()
        )

    def delete(self, token_obj):
        self.db.delete(token_obj)
        self.db.commit()
