# Engineering guide

FastAPI WebSocket chat demo with Redis pub/sub, room presence and PostgreSQL message history.

## Code tour

- [backend/app/main.py](backend/app/main.py)
- [backend/app/hub.py](backend/app/hub.py)
- [backend/app/auth.py](backend/app/auth.py)
- [.github/workflows/ci.yml](.github/workflows/ci.yml)

## Scope and verification

Realtime architecture demo. CI builds the images; token compatibility, presence and slow-client behavior require runtime verification.

[Current CI runs](https://github.com/umairjutt/realtime-chat-fastapi/actions). A workflow definition or build result does not establish that all runtime scenarios pass. The README contains development commands; unfinished setup and behavior need completion before production deployment.

## Maintainer

[Umair Jutt](https://github.com/umairjutt). Frameworks and dependencies retain their own ownership and licensing.
