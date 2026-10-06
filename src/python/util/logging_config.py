import logging


LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(level: int | str = logging.WARNING) -> None:
    """Configure console logging with a standard level or its string name."""
    if isinstance(level, str):
        try:
            level = LOG_LEVELS[level.upper()]
        except KeyError as error:
            choices = ", ".join(LOG_LEVELS)
            raise ValueError(f"Unknown logging level {level!r}; expected one of: {choices}") from error
    elif level not in LOG_LEVELS.values():
        raise ValueError(f"Unsupported numeric logging level: {level}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
