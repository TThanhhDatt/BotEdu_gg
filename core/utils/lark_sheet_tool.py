# core/utils/lark_sheet_tool.py

import os
import json
import requests
from core.graph.state import AgentState
from log.logger_config import setup_logging

logger = setup_logging(__name__)

# Lấy thông tin từ biến môi trường
APP_ID = os.getenv("LARK_APP_ID")
APP_SECRET = os.getenv("LARK_APP_SECRET")
BASE_ID = os.getenv("LARK_BASE_ID")
TABLE_ID = os.getenv("LARK_TABLE_ID")

def _get_tenant_access_token():
    """Lấy token xác thực từ Lark."""
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("code") == 0:
            logger.info("Lấy Tenant Access Token thành công.")
            return data.get("tenant_access_token")
        else:
            logger.error(f"Lỗi khi lấy token từ Lark: {data.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng khi gọi API lấy token: {e}")
        return None

def add_complaint_to_lark_sheet(state: AgentState) -> str | None:
    """
    Ghi thông tin khiếu nại vào một dòng mới trong Lark Sheet.
    """
    token = _get_tenant_access_token()
    if not token:
        return None

    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{BASE_ID}/tables/{TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    
    # Chuyển đổi state và messages thành chuỗi JSON để lưu
    chat_histories_str = json.dumps([msg.dict() for msg in state.get("messages", [])], ensure_ascii=False)
    state_str = json.dumps(state, ensure_ascii=False, default=str)

    # Quan trọng: Tên các trường (ví dụ: "Student ID", "Tên") phải khớp chính xác
    # với tên các cột trong Lark Sheet của bạn.
    payload = {
        "fields": {
            "Student ID": state.get("student_id"),
            "Tên": state.get("name"),
            "SĐT": state.get("phone_number"),
            "Email": state.get("email"),
            "Lịch sử chat": chat_histories_str,
            "State Cuộc trò chuyện": state_str,
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") == 0:
            record_id = data.get("data", {}).get("record", {}).get("record_id")
            logger.success(f"Đã thêm thành công bản ghi vào Lark Sheet với Record ID: {record_id}")
            return record_id
        else:
            logger.error(f"Lỗi khi ghi dữ liệu vào Lark Sheet: {data.get('msg')}")
            return None
    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng khi gọi API ghi dữ liệu Lark Sheet: {e}")
        return None