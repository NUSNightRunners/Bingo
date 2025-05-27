from app import db

class SpyScore(db.Model):
    __tablename__ = 'spy_scores'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    score = db.Column(db.Integer, default=0, nullable=False)

    user = db.relationship("User", backref="spy_score")
