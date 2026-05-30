import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import decode_token, hash_password, issue_token, verify_password
from .db import Message, Room, Session, User, get_db, init_db
from .hub import Connection, hub


class LoginIn(BaseModel):
    username: str
    password: str


class RoomIn(BaseModel):
    name: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    async with Session() as s:
        if (await s.execute(select(User))).first() is None:
            for u in ("alice", "bob", "charlie"):
                s.add(User(username=u, password_hash=hash_password("password")))
            s.add(Room(name="general"))
            await s.commit()
    await hub.start()
    yield
    await hub.stop()


app = FastAPI(title="Realtime Chat", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False,
)


@app.post("/auth/login")
async def login(body: LoginIn, session: AsyncSession = Depends(get_db)):
    r = await session.execute(select(User).where(User.username == body.username))
    user = r.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    return {"token": issue_token(user), "username": user.username}


@app.get("/rooms")
async def list_rooms(session: AsyncSession = Depends(get_db)):
    r = await session.execute(select(Room).order_by(Room.id))
    return [{"id": row.id, "name": row.name} for row in r.scalars().all()]


@app.post("/rooms", status_code=201)
async def create_room(body: RoomIn, session: AsyncSession = Depends(get_db)):
    room = Room(name=body.name)
    session.add(room)
    await session.commit()
    return {"id": room.id, "name": room.name}


@app.get("/rooms/{room_id}/messages")
async def list_messages(room_id: int, session: AsyncSession = Depends(get_db)):
    r = await session.execute(
        select(Message).where(Message.room_id == room_id).order_by(Message.id.desc()).limit(50)
    )
    msgs = list(reversed(r.scalars().all()))
    return [
        {"user": m.user.username, "text": m.text, "ts": m.created_at.isoformat() if m.created_at else None}
        for m in msgs
    ]


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(ws: WebSocket, room_id: int, token: str):
    payload = decode_token(token)
    username = payload["username"]
    user_id = payload["sub"]

    await ws.accept()
    conn = Connection(ws, username)
    writer_task = asyncio.create_task(conn.writer())

    await hub.join(room_id, conn)
    try:
        while True:
            data = await ws.receive_json()
            mtype = data.get("type")

            if mtype == "message":
                text = (data.get("text") or "").strip()
                if not text:
                    continue
                async with Session() as session:
                    session.add(Message(room_id=room_id, user_id=user_id, text=text))
                    await session.commit()
                await hub.publish(room_id, {
                    "type": "message",
                    "user": username,
                    "text": text,
                    "ts": datetime.now(tz=timezone.utc).isoformat(),
                })

            elif mtype == "typing":
                await hub.publish(room_id, {"type": "typing", "user": username, "value": bool(data.get("value"))})

    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(room_id, conn)
        writer_task.cancel()
