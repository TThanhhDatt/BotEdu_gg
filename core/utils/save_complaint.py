# core/utils/save_complaint.py

import json
from database.connection import supabase_client
from core.graph.state import AgentState
from log.logger_config import setup_logging

logger = setup_logging(__name__)

def save_complaint_to_db(state: AgentState) -> int | None:
    """
    Lưu thông tin chi tiết của một phiên trò chuyện khiếu nại vào bảng 'complaints' trong Supabase.

    Args:
        state (AgentState): Trạng thái hiện tại của cuộc trò chuyện.

    Returns:
        int | None: ID của bản ghi khiếu nại vừa được tạo, hoặc None nếu thất bại.
    """
    try:
        # Chuyển đổi message objects thành dictionary để lưu trữ dưới dạng JSON
        chat_histories = [msg.dict() for msg in state.get("messages", [])]

        payload = {
            "student_id": state.get("student_id"),
            "name": state.get("name"),
            "phone": state.get("phone_number"),
            "email": state.get("email"),
            "chat_histories": json.dumps(chat_histories, ensure_ascii=False),
            "state": json.dumps(state, ensure_ascii=False, default=str) # Chuyển đổi state thành chuỗi JSON
        }

        response = supabase_client.table("complaints").insert(payload).execute()

        if response.data:
            complaint_id = response.data[0]['id']
            logger.success(f"Đã lưu thành công khiếu nại với ID: {complaint_id}")
            return complaint_id
        else:
            logger.error(f"Không thể lưu khiếu nại vào CSDL. Phản hồi: {response}")
            return None
            
    except Exception as e:
        logger.error(f"Lỗi khi lưu khiếu nại vào CSDL: {e}")
        return None