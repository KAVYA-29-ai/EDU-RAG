"""
Vercel Serverless Function — entry point for FastAPI backend.
"""
import sys
import os

# ← YEH ADD KARO — backend folder ko path mein daalo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.main import app
