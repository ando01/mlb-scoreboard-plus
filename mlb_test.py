import asyncio, sys, logging
logging.basicConfig(level=logging.INFO)
sys.path.insert(0, '/home/mlb/mlb-scoreboard-plus')
from src.api.mlb_client import MLBAPIClient

async def test():
    client = MLBAPIClient()
    await client.__aenter__()
    print("Session created OK")
    ids = await client.get_todays_games()
    print(f"Game IDs ({len(ids)}): {ids}")
    await client.__aexit__(None, None, None)

asyncio.run(test())
