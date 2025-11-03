from datetime import datetime

class RoutesException(Exception):
    def __str__(self):
        return "Error at route level"

    class NoUser(Exception):
        def __str__(self):
            return "Error in returning data"

    class NotFound(Exception):
        def __str__(self):
            return "Ressource not found"

class AuthException(Exception):
    def __str__(self):
        return "Error during authentication process"

    class Unauthorized(Exception):
        def __str__(self):
            return "User is not authorized to access this resource."

