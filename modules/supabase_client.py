# modules/supabase_client.py

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Supabase credentials are missing. "
                       "Check SUPABASE_URL and SUPABASE_ANON_KEY in your .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
