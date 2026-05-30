"""Connection hub that bridges local WebSockets and Redis Pub/Sub.

Every worker process holds local connections (asyncio Queues). To broadcast
across workers we publish to `room:{id}` channels on Redis and a single
subscriber per worker dispatches messages to its local sockets.
"""
import asyncio
import json
from typing import Dict, Set

from redis import asyncio as aioredis
from starlette.websockets import WebSocket, WebSocketState

from .config import settings


class Hub:
    def __init__(self) -> None:
        self.local: Dict[int, Set["Connection"]] = {}
        self.redis: aioredis.Redis | None = None
        self.pubsub: aioredis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()

    async def join(self, room_id: int, conn: "Connection") -> None:
        async with self._lock:
            if room_id not in self.local:
                self.local[room_id] = set()
                await self.pubsub.subscribe(f"room:{room_id}")
            self.local[room_id].add(conn)

        await self.redis.sadd(f"presence:{room_id}", conn.username)
        await self.redis.expire(f"presence:{room_id}", 60)
        await self._broadcast_presence(room_id)

    async def leave(self, room_id: int, conn: "Connection") -> None:
        async with self._lock:
            if room_id in self.local and conn in self.local[room_id]:
                self.local[room_id].remove(conn)
                if not self.local[room_id]:
                    del self.local[room_id]
                    await self.pubsub.unsubscribe(f"room:{room_id}")

        await self.redis.srem(f"presence:{room_id}", conn.username)
        await self._broadcast_presence(room_id)

    async def publish(self, room_id: int, payload: dict) -> None:
        await self.redis.publish(f"room:{room_id}", json.dumps(payload))

    async def _broadcast_presence(self, room_id: int) -> None:
        members = await self.redis.smembers(f"presence:{room_id}")
        await self.publish(room_id, {"type": "presence", "online": sorted(members)})

    async def _listen(self) -> None:
        assert self.pubsub is not None
        async for message in self.pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                channel: str = message["channel"]
                room_id = int(channel.split(":")[1])
                payload = json.loads(message["data"])
            except (KeyError, ValueError, json.JSONDecodeError):
                continue

            for conn in list(self.local.get(room_id, set())):
                conn.send_nowait(payload)


class Connection:
    def __init__(self, ws: WebSocket, username: str) -> None:
        self.ws = ws
        self.username = username
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    def send_nowait(self, payload: dict) -> None:
        try:
            self.queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # backpressure: drop oldest semantics could be added

    async def writer(self) -> None:
        while True:
            payload = await self.queue.get()
            if self.ws.application_state != WebSocketState.CONNECTED:
                return
            await self.ws.send_json(payload)


hub = Hub()
