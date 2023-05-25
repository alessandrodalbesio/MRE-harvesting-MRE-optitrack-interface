import logging 

# Logging functions
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class logger:
    def __init__(self, log_on_stout = False):
        self.log_on_stout = log_on_stout

        self.logger = logging.getLogger('OptitrackConnection')
        self.logger.setLevel(logging.DEBUG)

        # Create file handler
        handler = logging.FileHandler('logs.log')
        handler.setLevel(logging.INFO)
        self.logger.addHandler(handler)

        # Create output handler
        if log_on_stout is True:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            format = logging.Formatter(bcolors.BOLD + "[%(levelname)s]" + bcolors.ENDC + " %(message)s")
            handler.setFormatter(format)
            self.logger.addHandler(handler)

    def get_log_on_stout(self):
        return self.log_on_stout

    def debug(self, text):
        self.logger.debug(text)

    def info(self, text):
        self.logger.info(text)

    def error(self, text):
        self.logger.error(text)