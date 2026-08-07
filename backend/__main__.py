"""
Entry Point — Main module to run the Vigilant ASGI server.
"""

import logging
import uvicorn

from backend.app import create_app
from backend.infrastructure.config.settings import load_settings
from backend.infrastructure.telemetry.logging import setup_logger

logger = setup_logger("vigilant")

def main() -> None:
    """Run the Vigilant ASGI server."""
    settings = load_settings()
    logger.info("Starting %s on %s:%d", settings.product_name, settings.host, settings.port)
    
    app = create_app()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info", access_log=False)

if __name__ == "__main__":
    main()
