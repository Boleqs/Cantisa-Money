class RoutesException(Exception):
    def __str__(self):
        return "Error at route level"

    class NoUser(Exception):
        def __str__(self):
            return "Error in returning data"


