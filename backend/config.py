# Aggregation of all configs for Flask App
from database.config import db_url

class Config:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = db_url

