import asyncio
import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "testVictima" / "server.py"


def load_victim_server(unique_name="victim_server_runner"):
    spec = importlib.util.spec_from_file_location(unique_name, SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def main():
    server = load_victim_server()
    temp_dir = tempfile.TemporaryDirectory()
    registry_dir = Path(temp_dir.name) / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    server.REGISTRY_DIR = str(registry_dir)
    server.USERS_FILE = str(registry_dir / "user_registry.json")
    server.POSTS_FILE = str(registry_dir / "posts_registry.json")
    server.SESSIONS_FILE = str(registry_dir / "session_registry.json")
    server.seed_if_needed()

    app = server.web.Application()
    server.setup_routes(app)
    runner = server.web.AppRunner(app)
    await runner.setup()
    site = server.web.TCPSite(runner, "127.0.0.1", 7070)
    await site.start()
    print("Victim app running at http://127.0.0.1:7070/")

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
        temp_dir.cleanup()


if __name__ == "__main__":
    asyncio.run(main())