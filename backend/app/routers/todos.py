from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import todos as todos_service

router = APIRouter()


@router.get("/api/todos")
async def get_todos():
    return {
        "items": todos_service.list_todos(),
        "statuses": todos_service.STATUSES,
        "priorities": todos_service.PRIORITIES,
    }


class AddTodoBody(BaseModel):
    text: str
    priority: str = todos_service.DEFAULT_PRIORITY


@router.post("/api/todos")
async def add_todo(body: AddTodoBody):
    try:
        return todos_service.add_todo(body.text, body.priority)
    except ValueError as e:
        raise HTTPException(400, str(e))


class ReorderBody(BaseModel):
    order: list[str]


@router.post("/api/todos/reorder")
async def reorder_todos(body: ReorderBody):
    try:
        return {"items": todos_service.reorder_todos(body.order)}
    except ValueError as e:
        raise HTTPException(400, str(e))


class SetStatusBody(BaseModel):
    status: str


@router.post("/api/todos/{item_id}/status")
async def set_todo_status(item_id: str, body: SetStatusBody):
    try:
        return todos_service.set_status(item_id, body.status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "Objective not found.")


class SetPriorityBody(BaseModel):
    priority: str


@router.post("/api/todos/{item_id}/priority")
async def set_todo_priority(item_id: str, body: SetPriorityBody):
    try:
        return todos_service.set_priority(item_id, body.priority)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError:
        raise HTTPException(404, "Objective not found.")


class SetBlockerBody(BaseModel):
    blocker: str


@router.post("/api/todos/{item_id}/blocker")
async def set_todo_blocker(item_id: str, body: SetBlockerBody):
    try:
        return todos_service.set_blocker(item_id, body.blocker)
    except KeyError:
        raise HTTPException(404, "Objective not found.")


@router.delete("/api/todos/{item_id}")
async def delete_todo(item_id: str):
    if not todos_service.delete_todo(item_id):
        raise HTTPException(404, "Objective not found.")
    return {"ok": True}
