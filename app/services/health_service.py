from sqlalchemy import text


class HealthService:
    def __init__(self, db):
        self.db = db

    def check_health(self):

        db_status = "disconnected"

        try:
            self.db.execute(text("SELECT 1"))

            db_status = "connected"

        except Exception:
            db_status = "disconnected"

        return db_status
