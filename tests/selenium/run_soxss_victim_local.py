import asyncio
import importlib.util
import tempfile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "twister" / "server.py"
sys.path.insert(0, str(ROOT))


def load_victim_server(unique_name="victim_server_runner"):
    spec = importlib.util.spec_from_file_location(unique_name, SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def main():
    import config
    import Socxss

    config.PUBLIC_HTTP_HOST = "127.0.0.1"
    config.PUBLIC_WS_HOST = "127.0.0.1"
    config.PUBLIC_HTTP_PORT = config.HTTP_PORT
    config.PUBLIC_WS_PORT = config.WS_PORT

    victim = load_victim_server()
    temp_dir = tempfile.TemporaryDirectory()
    registry_dir = Path(temp_dir.name) / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    victim.REGISTRY_DIR = str(registry_dir)
    victim.USERS_FILE = str(registry_dir / "user_registry.json")
    victim.POSTS_FILE = str(registry_dir / "posts_registry.json")
    victim.SESSIONS_FILE = str(registry_dir / "session_registry.json")
    victim.seed_if_needed()

    victim_app = victim.web.Application()
    victim.setup_routes(victim_app)
    victim_runner = victim.web.AppRunner(victim_app)
    await victim_runner.setup()
    victim_site = victim.web.TCPSite(victim_runner, "127.0.0.1", 7070)
    await victim_site.start()

    print("Victim app running at http://127.0.0.1:7070/")

    try:
        await Socxss.main()
    finally:
        await victim_runner.cleanup()
        temp_dir.cleanup()


if __name__ == "__main__":
    asyncio.run(main())