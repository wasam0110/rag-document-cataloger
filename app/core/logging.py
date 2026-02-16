"""
Centralized logging configuration for the application.

Configures Python's built-in logging to write INFO-level (and above)
messages to both stdout and a persistent `app.log` file.  Every other
module should import `logger` from here instead of creating its own.
"""

import logging
import sys


def setup_logging():
    """Configure the root logger with console and file handlers.

    - StreamHandler → prints to stdout (visible in terminal / Docker logs).
    - FileHandler   → appends to ``app.log`` for persistent diagnostics.

    The format includes timestamp, logger name, severity, and the message.
    """
    logging.basicConfig(
        level=logging.INFO,  # Capture INFO, WARNING, ERROR, CRITICAL
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),   # Console output
            logging.FileHandler("app.log"),       # Persistent log file
        ]
    )


# Execute logging setup immediately on module import so that any
# subsequent `import logger` gets a fully-configured logging system.
setup_logging()

# Export a named logger instance that all application modules share.
# Using a custom name ("rag-cataloger") makes it easy to filter in
# multi-service environments.
logger = logging.getLogger("rag-cataloger")