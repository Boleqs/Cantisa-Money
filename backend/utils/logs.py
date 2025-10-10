from datetime import datetime
from ..config import VAR_LOG_FILES


def log(message: str, filename, separator=False):
    if not filename in VAR_LOG_FILES:
        #TODO: create exception
        raise Exception
    with open(f"{VAR_LOG_FILES[filename]}", 'a+', encoding="utf-8") as logfile:
        if separator:
            logfile.write(f"\n\n---------------      ---------------\n\n")
        logfile.write(f"{filename} | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} : {message}\n")
