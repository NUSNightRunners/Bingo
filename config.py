import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'CgyLoveChina'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///bingo.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False