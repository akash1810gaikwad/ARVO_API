from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from config.mysql_database import get_mysql_db
from models.mysql_models import Customer, ChildSimCard, ChildLocation, ChildAlert
from typing import Dict, Set, Optional
from utils.logger import logger
from datetime import datetime
import json
import jwt
from config.settings import settings

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time communication"""
    
    def __init__(self):
        # Store active connections: {customer_id: Set[WebSocket]}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Store child connections: {msisdn: WebSocket}
        self.child_connections: Dict[str, WebSocket] = {}
        # Store rooms: {room_id: Set[WebSocket]}
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # Store connection metadata: {WebSocket: dict}
        self.connection_metadata: Dict[WebSocket, dict] = {}
    
    async def connect_parent(self, customer_id: int, websocket: WebSocket, db: Session):
        """Connect a parent user"""
        await websocket.accept()
        if customer_id not in self.active_connections:
            self.active_connections[customer_id] = set()
        self.active_connections[customer_id].add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "type": "parent",
            "customer_id": customer_id,
            "connected_at": datetime.utcnow()
        }
        
        # Join parent's room
        room_id = f"parent_{customer_id}"
        await self.join_room(websocket, room_id)
        
        logger.info(f"Parent {customer_id} connected via WebSocket")
    
    async def connect_child(self, msisdn: str, websocket: WebSocket, db: Session):
        """Connect a child device"""
        await websocket.accept()
        self.child_connections[msisdn] = websocket
        
        # Get child info
        child_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == msisdn,
            ChildSimCard.is_active == True
        ).first()
        
        customer_id = child_sim.subscriber.customer_id if child_sim and child_sim.subscriber else None
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "type": "child",
            "msisdn": msisdn,
            "customer_id": customer_id,
            "child_name": child_sim.child_name if child_sim else None,
            "connected_at": datetime.utcnow()
        }
        
        # Join child's room and parent's room
        await self.join_room(websocket, f"child_{msisdn}")
        if customer_id:
            await self.join_room(websocket, f"parent_{customer_id}")
        
        logger.info(f"Child {msisdn} connected via WebSocket")
    
    def disconnect_parent(self, customer_id: int, websocket: WebSocket):
        """Disconnect a parent user"""
        if customer_id in self.active_connections:
            self.active_connections[customer_id].discard(websocket)
            if not self.active_connections[customer_id]:
                del self.active_connections[customer_id]
        
        # Remove from rooms and metadata
        self._cleanup_connection(websocket)
        logger.info(f"Parent {customer_id} disconnected from WebSocket")
    
    def disconnect_child(self, msisdn: str, websocket: Optional[WebSocket] = None):
        """Disconnect a child device"""
        if msisdn in self.child_connections:
            ws = self.child_connections[msisdn]
            del self.child_connections[msisdn]
            self._cleanup_connection(ws)
        elif websocket:
            self._cleanup_connection(websocket)
        logger.info(f"Child {msisdn} disconnected from WebSocket")
    
    def _cleanup_connection(self, websocket: WebSocket):
        """Clean up connection from all rooms and metadata"""
        # Remove from all rooms
        for room_id, connections in list(self.rooms.items()):
            connections.discard(websocket)
            if not connections:
                del self.rooms[room_id]
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
    
    async def join_room(self, websocket: WebSocket, room_id: str):
        """Add connection to a room"""
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(websocket)
        logger.debug(f"Connection joined room: {room_id}")
    
    async def leave_room(self, websocket: WebSocket, room_id: str):
        """Remove connection from a room"""
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        logger.debug(f"Connection left room: {room_id}")
    
    async def send_to_parent(self, customer_id: int, message: dict):
        """Send message to all parent's connections"""
        if customer_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[customer_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to parent {customer_id}: {str(e)}")
                    disconnected.add(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.active_connections[customer_id].discard(conn)
    
    async def send_to_child(self, msisdn: str, message: dict):
        """Send message to a child device"""
        if msisdn in self.child_connections:
            try:
                await self.child_connections[msisdn].send_json(message)
            except Exception as e:
                logger.error(f"Error sending to child {msisdn}: {str(e)}")
                self.disconnect_child(msisdn)
    
    async def broadcast_to_parent_children(self, customer_id: int, message: dict, db: Session):
        """Broadcast message to all children of a parent"""
        from models.mysql_models import Subscriber
        
        # Get subscriber
        subscriber = db.query(Subscriber).filter(
            Subscriber.customer_id == customer_id
        ).first()
        
        if not subscriber:
            return
        
        # Get all child SIM cards
        child_sims = db.query(ChildSimCard).filter(
            ChildSimCard.subscriber_id == subscriber.id,
            ChildSimCard.is_active == True
        ).all()
        
        # Send to each child
        for child_sim in child_sims:
            if child_sim.msisdn:
                await self.send_to_child(child_sim.msisdn, message)
    
    async def broadcast_to_room(self, room_id: str, message: dict, exclude: Optional[WebSocket] = None):
        """Broadcast message to all connections in a room"""
        if room_id not in self.rooms:
            return
        
        disconnected = set()
        for connection in self.rooms[room_id]:
            if connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to room {room_id}: {str(e)}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.rooms[room_id].discard(conn)
    
    async def send_chat_message(self, from_msisdn: str, to_msisdn: str, message: str, db: Session):
        """Send chat message between parent and child"""
        # Get sender info
        sender_sim = db.query(ChildSimCard).filter(
            ChildSimCard.msisdn == from_msisdn
        ).first()
        
        sender_name = sender_sim.child_name if sender_sim else from_msisdn
        
        # Send to recipient
        await self.send_to_child(to_msisdn, {
            "type": "chat",
            "from": from_msisdn,
            "from_name": sender_name,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def get_online_children(self, customer_id: int) -> list:
        """Get list of online children for a parent"""
        online_children = []
        for msisdn, ws in self.child_connections.items():
            metadata = self.connection_metadata.get(ws, {})
            if metadata.get("customer_id") == customer_id:
                online_children.append({
                    "msisdn": msisdn,
                    "child_name": metadata.get("child_name"),
                    "connected_at": metadata.get("connected_at").isoformat() if metadata.get("connected_at") else None
                })
        return online_children


# Global connection manager
manager = ConnectionManager()


def verify_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.InvalidTokenError:
        return None


@router.websocket("/parent")
async def websocket_parent_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_mysql_db)
):
    """
    WebSocket endpoint for parent users
    Receives real-time updates about children (location, alerts, status)
    Can send commands to children
    """
    # Verify token
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    customer_id = int(payload.get("sub"))
    
    # Verify customer exists
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer or not customer.is_active:
        await websocket.close(code=1008, reason="Invalid customer")
        return
    
    # Connect parent
    await manager.connect_parent(customer_id, websocket, db)
    
    try:
        # Get online children
        online_children = manager.get_online_children(customer_id)
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to parent WebSocket",
            "customer_id": customer_id,
            "online_children": online_children
        })
        
        # Listen for messages from parent
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "ping":
                # Respond to ping
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "join":
                # Join a specific room
                room_id = message.get("room")
                if room_id:
                    await manager.join_room(websocket, room_id)
                    await websocket.send_json({
                        "type": "joined",
                        "room": room_id
                    })
            
            elif message_type == "command":
                # Parent sending command to child
                to_msisdn = message.get("to")
                action = message.get("action")
                
                if to_msisdn and action:
                    await manager.send_to_child(to_msisdn, {
                        "type": "command",
                        "action": action,
                        "data": message.get("data", {}),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await websocket.send_json({
                        "type": "command_sent",
                        "to": to_msisdn,
                        "action": action
                    })
            
            elif message_type == "chat":
                # Parent sending chat message to child
                to_msisdn = message.get("to")
                chat_message = message.get("message")
                
                if to_msisdn and chat_message:
                    await manager.send_to_child(to_msisdn, {
                        "type": "chat",
                        "from": "parent",
                        "from_name": customer.full_name,
                        "message": chat_message,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await websocket.send_json({
                        "type": "chat_sent",
                        "to": to_msisdn
                    })
            
            elif message_type == "location_request":
                # Parent requesting child's location
                msisdn = message.get("msisdn")
                
                if msisdn:
                    await manager.send_to_child(msisdn, {
                        "type": "location_request",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await websocket.send_json({
                        "type": "location_requested",
                        "msisdn": msisdn
                    })
            
            elif message_type == "get_online_children":
                # Get list of online children
                online_children = manager.get_online_children(customer_id)
                await websocket.send_json({
                    "type": "online_children",
                    "children": online_children
                })
            
            else:
                logger.warning(f"Unknown message type from parent {customer_id}: {message_type}")
    
    except WebSocketDisconnect:
        manager.disconnect_parent(customer_id, websocket)
    except Exception as e:
        logger.error(f"Error in parent WebSocket: {str(e)}")
        manager.disconnect_parent(customer_id, websocket)


@router.websocket("/child")
async def websocket_child_endpoint(
    websocket: WebSocket,
    msisdn: str = Query(...),
    db: Session = Depends(get_mysql_db)
):
    """
    WebSocket endpoint for child devices
    Sends real-time location updates
    Receives commands from parent
    """
    # Verify child SIM exists
    child_sim = db.query(ChildSimCard).filter(
        ChildSimCard.msisdn == msisdn,
        ChildSimCard.is_active == True
    ).first()
    
    if not child_sim:
        await websocket.close(code=1008, reason="Invalid MSISDN")
        return
    
    # Get customer ID
    customer_id = child_sim.subscriber.customer_id if child_sim.subscriber else None
    
    # Connect child
    await manager.connect_child(msisdn, websocket, db)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to child WebSocket",
            "msisdn": msisdn,
            "child_name": child_sim.child_name
        })
        
        # Notify parent that child is online
        if customer_id:
            await manager.send_to_parent(customer_id, {
                "type": "child_connected",
                "msisdn": msisdn,
                "child_name": child_sim.child_name,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Listen for messages from child
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "ping":
                # Respond to ping
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "join":
                # Join a specific room
                room_id = message.get("room")
                if room_id:
                    await manager.join_room(websocket, room_id)
                    await websocket.send_json({
                        "type": "joined",
                        "room": room_id
                    })
            
            elif message_type == "location":
                # Child sending location update (Socket.IO style)
                lat = message.get("lat")
                lng = message.get("lng")
                battery = message.get("battery")
                speed = message.get("speed", 0)
                accuracy = message.get("accuracy")
                
                if lat and lng:
                    # Save to database
                    location = ChildLocation(
                        msisdn=msisdn,
                        latitude=lat,
                        longitude=lng,
                        speed=speed,
                        battery=battery,
                        accuracy=accuracy,
                        provider=message.get("provider", "gps")
                    )
                    db.add(location)
                    db.commit()
                    
                    # Forward to parent
                    if customer_id:
                        await manager.send_to_parent(customer_id, {
                            "type": "location",
                            "msisdn": msisdn,
                            "child_name": child_sim.child_name,
                            "lat": lat,
                            "lng": lng,
                            "battery": battery,
                            "speed": speed,
                            "accuracy": accuracy,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                    await websocket.send_json({
                        "type": "location_saved",
                        "message": "Location updated"
                    })
            
            elif message_type == "sos":
                # Child sending SOS
                lat = message.get("lat")
                lng = message.get("lng")
                sos_message = message.get("message", "Emergency SOS")
                
                # Create SOS alert in database
                alert = ChildAlert(
                    msisdn=msisdn,
                    child_sim_card_id=child_sim.id,
                    customer_id=customer_id,
                    alert_type="SOS",
                    message=sos_message,
                    latitude=lat,
                    longitude=lng,
                    is_read=False
                )
                db.add(alert)
                db.commit()
                
                # Forward to parent
                if customer_id:
                    await manager.send_to_parent(customer_id, {
                        "type": "sos",
                        "msisdn": msisdn,
                        "child_name": child_sim.child_name,
                        "message": sos_message,
                        "lat": lat,
                        "lng": lng,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                await websocket.send_json({
                    "type": "sos_received",
                    "message": "SOS alert sent to parent"
                })
            
            elif message_type == "chat":
                # Child sending chat message
                chat_message = message.get("message")
                
                if chat_message and customer_id:
                    await manager.send_to_parent(customer_id, {
                        "type": "chat",
                        "from": msisdn,
                        "from_name": child_sim.child_name,
                        "message": chat_message,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await websocket.send_json({
                        "type": "chat_sent",
                        "message": "Message sent to parent"
                    })
            
            else:
                logger.warning(f"Unknown message type from child {msisdn}: {message_type}")
    
    except WebSocketDisconnect:
        manager.disconnect_child(msisdn, websocket)
        # Notify parent that child disconnected
        if customer_id:
            await manager.send_to_parent(customer_id, {
                "type": "child_disconnected",
                "msisdn": msisdn,
                "child_name": child_sim.child_name,
                "timestamp": datetime.utcnow().isoformat()
            })
    except Exception as e:
        logger.error(f"Error in child WebSocket: {str(e)}")
        manager.disconnect_child(msisdn, websocket)


# Helper function to send alerts via WebSocket (can be called from other routes)
async def send_alert_to_parent(customer_id: int, alert_data: dict):
    """Send alert to parent via WebSocket"""
    await manager.send_to_parent(customer_id, {
        "type": "alert",
        **alert_data
    })
