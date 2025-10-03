import uuid
import json
import asyncio

from langgraph.graph import StateGraph

from core.graph.state import init_state
from services.utils import get_uuid, update_uuid

from log.logger_config import setup_logging

logger = setup_logging(__name__)

async def _get_or_create_uuid(chat_id: str) -> str:
    """
    Lấy `uuid` hiện tại của khách theo `chat_id`, nếu chưa tồn tại thì tạo mới và lưu.

    Args:
        chat_id (str): Định danh cuộc hội thoại/khách hàng.

    Returns:
        str: UUID hiện có hoặc mới tạo.
    """
    current_uuid = await get_uuid(chat_id=chat_id)
    
    if not current_uuid:
        new_uuid = str(uuid.uuid4())
        await update_uuid(chat_id=chat_id, new_uuid=new_uuid)
        return new_uuid

    return current_uuid


async def handle_normal_chat(
    user_input: str,
    chat_id: str,
    customer: dict,
    graph: StateGraph
):
    """
    Xử lý luồng chat thông thường: nạp state, cập nhật thông tin khách, gọi graph và trả về `events`.

    Args:
        user_input (str): Nội dung người dùng nhập.
        chat_id (str): Mã cuộc hội thoại.
        customer (dict): Thông tin khách hàng lấy từ DB.
        graph (StateGraph): Đồ thị tác vụ chính để suy luận.

    Returns:
        tuple[Any, str] | tuple[None, None]: Cặp (events, thread_id) hoặc (None, None) nếu lỗi.
    """
    try:
        thread_id = await _get_or_create_uuid(chat_id=chat_id)

        if not thread_id:
            logger.error("Lỗi ở cấp DB -> không lấy được uuid")
            return None, None

        logger.info(f"Lấy được uuid của khách: {chat_id} là {thread_id}")

        config = {"configurable": {"thread_id": thread_id}}

        state = (graph.get_state(config).values 
                 if graph.get_state(config).values 
                 else init_state())

        state["user_input"] = user_input
        state["chat_id"] = chat_id
        
        state["student_id"] = customer["student_id"]
        state["name"] = customer["name"]
        state["phone_number"] = customer["phone_number"]
        state["email"] = customer["email"]

        events = graph.astream(state, config=config)

        return events, thread_id
    
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise
        
async def handle_new_chat(
    chat_id: str
):
    """
    Khởi tạo phiên chat mới (reset): cập nhật `uuid` mới trong DB và phát thông báo SSE.

    Args:
        chat_id (str): Định danh cuộc hội thoại.

    Yields:
        str: Chuỗi SSE dạng `data: {...}` và token `[DONE]` khi hoàn tất.
    """
    try:
        new_uuid = str(uuid.uuid4())
        updated_uuid = await update_uuid(
            chat_id=chat_id,
            new_uuid=new_uuid
        )

        if not updated_uuid:
            logger.error("Lỗi ở cấp DB -> Không thể cập nhật uuid")
            error_dict = {"error": "Lỗi không thể cập nhật uuid"}
            
            yield f"data: {json.dumps(error_dict, ensure_ascii=False)}\n\n"
        else:
            logger.info(f"Cập nhật uuid của khách: {chat_id} là {updated_uuid}")

            response = (
                "Chào anh/chị, em rất vui được hỗ trợ anh/chị. Nếu anh/chị có thắc mắc hoặc "
                "cần tư vấn về các khóa học của trung tâm, hãy cho em biết nhé! Em rất sẵn lòng giúp đỡ.\n"
            )

            msg = {"content": response}
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        error_dict = {"error": str(e), "thread_id": updated_uuid}
        yield f"data: {json.dumps(error_dict, ensure_ascii=False)}\n\n"
        
    finally:
        await asyncio.sleep(0.01)
        yield "data: [DONE]\n\n"
        