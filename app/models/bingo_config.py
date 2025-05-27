from app import db

class BingoConfig(db.Model):
    __tablename__ = 'bingo_config'

    id = db.Column(db.Integer, primary_key=True, default=1)
    matrix_size = db.Column(db.Integer, nullable=False, default=5)
    spy_enabled = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
