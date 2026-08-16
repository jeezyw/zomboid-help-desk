from fastapi import APIRouter

from ..console_log import find_console_log, read_since
from ..log_patterns import classify_line

router = APIRouter()


@router.get("/api/logs")
async def logs(tail: int = 300, since: str | None = None):
    tail = max(1, min(tail, 5000))
    path = find_console_log()
    if not path:
        return {
            "lines": [], "cursor": since, "path": None,
            "error": "No server-console.txt (or Logs/*.txt) found under the configured Zomboid data path.",
        }

    offset = int(since) if since else None
    raw_lines, new_offset = read_since(path, offset, tail=tail)

    lines = [{"ts": "", "text": text, "category": classify_line(text)} for text in raw_lines]
    return {"lines": lines, "cursor": str(new_offset), "path": str(path), "error": None}
