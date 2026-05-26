import asyncio
import sys
from pathlib import Path

# Add project root to path so config and Socxss can be imported
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import config

# Override public endpoints for local Selenium execution.
config.PUBLIC_HTTP_HOST = "127.0.0.1"
config.PUBLIC_WS_HOST = "127.0.0.1"
config.PUBLIC_HTTP_PORT = config.HTTP_PORT
config.PUBLIC_WS_PORT = config.WS_PORT

import Socxss


if __name__ == "__main__":
    Socxss.clean_console()
    try:
        asyncio.run(Socxss.main())
    except KeyboardInterrupt:
        print("\nSOXSS local runner stopped.")
