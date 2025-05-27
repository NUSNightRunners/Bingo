from app import db

class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    result = db.Column(db.String(20), nullable=False)  # approved / rejected
    comment = db.Column(db.Text)
    is_spy_attack = db.Column(db.Boolean, default=False)

    reviewed_at = db.Column(db.DateTime, server_default=db.func.now())
