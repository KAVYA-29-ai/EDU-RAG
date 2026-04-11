"""
Vercel Serverless Function — entry point for FastAPI backend.
"""
import sys
import os

# Ensure backend modules take precedence over legacy root-level modules.
root_dir = os.path.join(os.path.dirname(__file__), '..')
backend_dir = os.path.join(root_dir, 'backend')

for path in (backend_dir, root_dir):
	if path in sys.path:
		sys.path.remove(path)

sys.path.insert(0, backend_dir)
sys.path.insert(1, root_dir)

from backend.main import app
