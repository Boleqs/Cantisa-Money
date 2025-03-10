class ApiUserError(Exception):
    def __str__(self):
        return "Error in returning data"