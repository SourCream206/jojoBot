"""
Migration script to add current_turn_user_id column to active_battles table.
Run this once to update your existing database.
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def add_turn_column():
    """Add current_turn_user_id column to active_battles table."""
    try:
        # Execute the ALTER TABLE command
        result = supabase.rpc('exec_sql', {
            'sql': '''
                ALTER TABLE active_battles 
                ADD COLUMN IF NOT EXISTS current_turn_user_id TEXT;
            '''
        }).execute()
        
        print("✅ Successfully added current_turn_user_id column to active_battles table!")
        return True
    except Exception as e:
        print(f"❌ Error adding column: {e}")
        print("\nManual SQL to run in Supabase SQL Editor:")
        print("ALTER TABLE active_battles ADD COLUMN IF NOT EXISTS current_turn_user_id TEXT;")
        return False

if __name__ == "__main__":
    print("Adding current_turn_user_id column to active_battles table...")
    add_turn_column()
