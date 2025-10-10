
def check_user_password(Users, user_name, password_hash):
    try:
        return Users.query.filter(Users.username == user_name).first().password_hash == password_hash
    except AttributeError:
        return False

def check_user_exist(Users, user_name):
    return bool(Users.query.filter(Users.username == user_name).first())
