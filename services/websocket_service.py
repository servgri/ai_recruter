"""WebSocket service for real-time updates."""

from flask_socketio import SocketIO, emit
from flask import request


def init_websocket(app, socketio: SocketIO):
    """
    Initialize WebSocket handlers.
    
    Args:
        app: Flask application
        socketio: SocketIO instance
    """
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        print(f"Client connected: {request.sid}")
        emit('connected', {'status': 'connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        print(f"Client disconnected: {request.sid}")
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        """
        Handle subscription to document updates.
        
        Expected data:
        {
            "doc_id": 123
        }
        """
        doc_id = data.get('doc_id')
        if doc_id:
            # Join room for this document
            from flask_socketio import join_room
            join_room(f"doc_{doc_id}", sid=request.sid)
            emit('subscribed', {'doc_id': doc_id, 'status': 'subscribed'})
