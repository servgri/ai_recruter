"""
WSGI entry point for production (e.g. Render, Gunicorn + eventlet).
Monkey-patch eventlet first so Flask-SocketIO works with async workers.
"""
import eventlet
eventlet.monkey_patch()

from app import app

# Gunicorn uses: gunicorn -k eventlet -w 1 --timeout 180 wsgi:app
