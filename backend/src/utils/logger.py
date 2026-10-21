import logging

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        color = self.COLORS.get(record.levelno, "")

        if color:
            record.levelname = f"{color}{original_levelname}{self.RESET}"

        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = ColoredFormatter(
        "[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    return logger
