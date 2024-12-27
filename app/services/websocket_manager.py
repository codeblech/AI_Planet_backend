from typing import Dict, Set
from fastapi import WebSocket

class WebSocketConnectionManager:
    """
    Manages WebSocket connections and session authorization.

    This class handles the lifecycle of WebSocket connections, including
    authorization, connection management, and message distribution.

    Attributes:
        active_websocket_connections (Dict[str, WebSocket]): Active WebSocket connections
        authorized_upload_sessions (Set[str]): Set of authorized session IDs
        established_websocket_sessions (Set[str]): Set of established WebSocket sessions
    """

    def __init__(self):
        self.active_websocket_connections: Dict[str, WebSocket] = {}
        self.authorized_upload_sessions: Set[str] = set()
        self.established_websocket_sessions: Set[str] = set()

    async def connect_websocket(self, websocket: WebSocket, session_id: str) -> bool:
        """
        Establish a WebSocket connection for an authorized session.

        Args:
            websocket (WebSocket): The WebSocket connection instance
            session_id (str): Session identifier

        Returns:
            bool: True if connection was successful, False otherwise
        """
        print(f"Attempting to connect session {session_id}")
        print(f"Authorized sessions: {self.authorized_upload_sessions}")
        if session_id not in self.authorized_upload_sessions:
            print(f"Session {session_id} not authorized")
            await websocket.close(code=1008, reason="Upload documents first")
            return False
        await websocket.accept()
        self.active_websocket_connections[session_id] = websocket
        self.established_websocket_sessions.add(session_id)
        print(f"Successfully connected session {session_id}")
        return True

    async def disconnect_websocket(self, session_id: str):
        if session_id in self.active_websocket_connections:
            del self.active_websocket_connections[session_id]

    async def send_websocket_message(self, message: str, session_id: str):
        if session_id in self.active_websocket_connections:
            await self.active_websocket_connections[session_id].send_text(message)

    def authorize_upload_session(self, session_id: str):
        self.authorized_upload_sessions.add(session_id)
        print(f"Authorized new session: {session_id}")

websocket_manager = WebSocketConnectionManager() 