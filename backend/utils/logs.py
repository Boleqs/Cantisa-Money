#TODO : a rework, ancienne fonction à moi (mal écrite)
def log(message: str, big=False, separator=False, dated=False):

    rator = f'\n'
    with open(f"{os.getcwd()}\\log.txt", 'a+', encoding="utf-8") as logfile:
        now = datetime.now()
        if big:
            rator = f"\n\n\n---------------   {now.strftime('%d/%m/%Y')}   ---------------\n\n\n"
        elif separator:
            rator = f"\n\n---------------   {now.strftime('%d/%m/%Y %H:%M:%S')}   ---------------\n"
        elif dated:
            logfile.write(rator)
            logfile.write(f"{now.strftime('%d/%m/%Y %H:%M:%S')} : {message}")
            return
        logfile.write(rator)
        logfile.write(message)
