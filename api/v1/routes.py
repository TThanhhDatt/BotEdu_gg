import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

import json
from typing import Any
from langchain_core.messages import AIMessage

from core.graph.state import init_state
from core.graph.build_graph import create_main_graph

router = APIRouter()
graph = create_main_graph()

class ChatRequest(BaseModel):
    chat_id: str
    user_input: str
    uuid: str

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Xử lý yêu cầu chat dạng streaming (v1).

    Args:
        request (ChatRequest): Thông tin phiên chat gồm `chat_id`, `user_input`, `uuid`.

    Returns:
        StreamingResponse: Dòng sự kiện SSE chứa nội dung phản hồi theo thời gian thực.
    """
    thread_id = str(request.uuid)
    config = {"configurable": {"thread_id": thread_id}}

    state = graph.get_state(config).values if graph.get_state(config).values else init_state()
    state["user_input"] = request.user_input
    state["chat_id"] = request.chat_id
    
    events = graph.astream(state, config=config)
    return StreamingResponse(
        stream_messages(events, thread_id),
        media_type="text/event-stream"
    )
    
    
async def stream_messages(events: Any, thread_id: str):
    """
    Chuyển đổi luồng sự kiện của graph thành SSE để client nhận theo thời gian thực.

    Args:
        events (Any): Async iterator sự kiện từ graph.astream.
        thread_id (str): Định danh luồng hội thoại.

    Yields:
        str: Chuỗi SSE dạng `data: {...}\n\n`.
    """
    last_printed = None
    closed = False

    try:
        async for data in events:
            for key, value in data.items():
                    messages = value.get("messages", [])
                    if not messages:
                        continue

                    last_msg = messages[-1]
                    if isinstance(last_msg, AIMessage):
                        content = last_msg.content.strip()
                        if content and content != last_printed:
                            last_printed = content
                            msg = {"content": content}
                            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                            await asyncio.sleep(0.01)  # slight delay for smoother streaming
    except GeneratorExit:
        closed = True
        raise
    except Exception as e:
        error_dict = {"error": str(e), "thread_id": thread_id}
        yield f"data: {json.dumps(error_dict, ensure_ascii=False)}\n\n"
    finally:
        if not closed:
            yield "data: [DONE]\n\n"