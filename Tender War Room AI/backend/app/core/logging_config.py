import logging
import sys
from pathlib import Path

# Create log directory if it doesn't exist
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

def setup_logging() -> None:
    # Setup formatter
    log_format = (
        "[%(asctime)s] %(levelname)s [%(name)s:%(metadata.json)d] - %(message)s"
    )
    # Actually metadata.json is a placeholder, let's use line number: %(lineno)d
    log_format = "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s"
    
    formatter = logging.Formatter(log_format)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # File Handler
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Set third-party library log levels
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.info("Logging configured successfully. File path: %s", LOG_FILE)
