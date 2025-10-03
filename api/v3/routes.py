from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.graph.graph_dependencies import get_graph
from core.graph.build_graph import create_main_graph
from services.utils import get_or_create_customer, stream_messages
from services.process_chat import handle_normal_chat, handle_new_chat

from log.logger_config import setup_logging

logger = setup_logging(__name__)

router = APIRouter()
# graph = Depends(get_graph)
graph = create_main_graph()

class ChatRequest(BaseModel):
    chat_id: str
    user_input: str

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        user_input = request.user_input
        chat_id = request.chat_id
        
        config = {
            "configurable": 
            {
                "thread_id": chat_id
            }
        }
        
        customer = await get_or_create_customer(chat_id=chat_id)
        
        logger.info(f"Lấy hoặc tạo mới khách: {customer}")
        logger.info(f"Tin nhắn của khách: {user_input}")

        if any(cmd in user_input for cmd in ["/start", "/restart"]):
            return StreamingResponse(
                handle_new_chat(chat_id=chat_id),
                media_type="text/event-stream"
            )

        events, thread_id = await handle_normal_chat(
            user_input=user_input,
            chat_id=chat_id,
            customer=customer,
            graph=graph
        )

        if events and thread_id:
            return StreamingResponse(
                stream_messages(events, thread_id),
                media_type="text/event-stream"
            )
            
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise