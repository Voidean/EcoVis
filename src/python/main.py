import logging

from application import App
from util.logging_config import configure_logging

if __name__ == "__main__":
    # TODO: Change the logging level before deployment.
    configure_logging(logging.INFO)
    App().run()
