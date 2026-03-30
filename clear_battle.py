import asyncio
import sys
import os

# Add current directory to path so we can import src modules
sys.path.insert(0, os.getcwd())

async def clear_user_battle():
    from src.db.client import _run_sync, db, delete_active_battle
    
    # Check what battles exist for this user
    user_id = '351552830936449024'
    print(f"Checking for active battles for user {user_id}...")
    
    try:
        res = await _run_sync(lambda: db().table('active_battles').select('*').or_(f'attacker_id.eq.{user_id},defender_id.eq.{user_id}').execute())
        battles = res.data or []
        
        if battles:
            print(f'Found {len(battles)} battles for user {user_id}')
            for battle in battles:
                print(f'Battle ID {battle["id"]}: started at {battle["started_at"]}, expires at {battle["expires_at"]}')
                await delete_active_battle(battle["id"])
                print(f'✅ Deleted battle {battle["id"]}')
        else:
            print(f'No active battles found for user {user_id}')
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(clear_user_battle())