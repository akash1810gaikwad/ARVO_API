import logging
import os
from pythonjsonlogger import jsonlogger
from config.settings import settings

# Disable SQLAlchemy logging IMMEDIATELY before anything else
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)


def setup_logger():
    """Setup application logger with JSON formatting"""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(settings.LOG_FILE_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create logger
    logger = logging.getLogger(settings.APP_NAME)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # JSON formatter
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(settings.LOG_FILE_PATH)
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logger()
