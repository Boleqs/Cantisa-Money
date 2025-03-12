from datetime import datetime

class RoutesException(Exception):
    def __str__(self):
        return "Error at route level"

    def as_json(self):
        return {'data': {'type'},
                'metadata' : {'date' : datetime.now()}}

    class NoUser(Exception):
        def __str__(self):
            return "Error in returning data"


