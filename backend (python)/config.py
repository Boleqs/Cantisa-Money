# Aggregation of all configs for Flask App
class Config:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = 'postgresql://dcantau:dcantau@localhost/test'

