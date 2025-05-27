from app import db
from app.models.user import User
from app.models.team import Team

class UserTeam(db.Model):
    __tablename__ = 'user_team'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    is_spy = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="team")
    team = db.relationship("Team", back_populates="members")
