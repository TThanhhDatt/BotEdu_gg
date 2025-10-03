# ChatbotCSKH/core/tools/notification_tool.py

from langchain_core.tools import tool
import requests
import json
import os
from log.logger_config import setup_logging # <-- Thêm import logger
import random
logger = setup_logging(__name__) # <-- Khởi tạo logger

LARK_WEBHOOK_URL = os.getenv("LARK_WEBHOOK_URL")
agent = ["Đạt CSKH", "Long CSKH", "Sinh CSKH"]
customer_agent = random.choice(agent)
admin = ["Đạt R&D", "Long R&D", "Sinh R&D"]
admin_agent = random.choice(admin)

@tool
def send_cskh_notification_tool(
    customer_name: str,
    customer_phone: str,
    issue_summary: str,
    chat_history_url: str
) -> str:
    """
    Gửi một Message Card tương tác đến kênh Lark của đội ngũ CSKH.
    """
    # --- BẮT ĐẦU THAY ĐỔI: Thêm logging để debug ---
    if not LARK_WEBHOOK_URL:
        logger.error("LARK_WEBHOOK_URL chưa được cấu hình trong file .env")
        return "LARK_WEBHOOK_URL chưa được cấu hình."

    logger.info(f"Đang gửi thông báo đến Lark Webhook: ...{LARK_WEBHOOK_URL[-10:]}")
    # --- KẾT THÚC THAY ĐỔI ---

    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "red",
                    "title": {"content": "🚨 YÊU CẦU HỖ TRỢ KHẨN CẤP", "tag": "plain_text"}
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"content": f"**Khách hàng: **{customer_name or 'Chưa có'}", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**SĐT: **{customer_phone or 'Chưa có'}", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**Nhân viên hỗ trợ: **{customer_agent}", "tag": "lark_md"}}
                        ]
                    },
                    {"tag": "div", "text": {"content": f"**Tóm tắt vấn đề:**\n{issue_summary}", "tag": "lark_md"}},
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": [
                            {"tag": "button", "text": {"content": "Xem Lịch sử & Tiếp nhận", "tag": "plain_text"}, "url": chat_history_url, "type": "primary"}
                        ]
                    }
                ]
            }
        }
        
        response = requests.post(LARK_WEBHOOK_URL, json=payload)
        
        response.raise_for_status()  # Dòng này sẽ báo lỗi nếu status code là 4xx hoặc 5xx
        
        response_json = response.json()
        if response_json.get("StatusCode") == 0:
            logger.success("Gửi thông báo đến Lark thành công!")
            return "Thông báo đã được gửi thành công đến đội ngũ CSKH trên Lark."
        else:
            # Ghi lại lỗi chi tiết từ Lark
            logger.error(f"Lark API trả về lỗi: {response_json.get('msg')}")
            return f"Gửi thông báo Lark thất bại: {response_json.get('msg')}"
            
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Lỗi HTTP khi gọi Lark Webhook: {http_err} - {response.text}")
        return f"Lỗi HTTP khi gửi thông báo Lark: {http_err}"
    except Exception as e:
        logger.error(f"Lỗi không xác định khi gửi thông báo Lark: {e}")
        return f"Lỗi không xác định khi gửi thông báo Lark: {str(e)}"

@tool
def send_altercourse_notification_tool(
    customer_name: str,
    customer_phone: str,
    issue_summary: str,
    chat_history_url: str
) -> str:
    """
    Gửi một Message Card tương tác đến kênh Lark của đội ngũ CSKH.
    """
    if not LARK_WEBHOOK_URL:
        logger.error("LARK_WEBHOOK_URL chưa được cấu hình trong file .env")
        return "LARK_WEBHOOK_URL chưa được cấu hình."

    logger.info(f"Đang gửi thông báo đến Lark Webhook: ...{LARK_WEBHOOK_URL[-10:]}")

    try:
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "template": "yellow",
                    "title": {"content": "🔔 THÔNG BÁO HỌC VIÊN HỦY KHÓA HỌC", "tag": "plain_text"}
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"content": f"**Khách hàng: **{customer_name or 'Chưa có'}", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**SĐT: **{customer_phone or 'Chưa có'}", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**Nhân viên hỗ trợ: **{admin_agent}", "tag": "lark_md"}}
                        ]
                    },
                    {"tag": "div", "text": {"content": f"**Nội dung cụ thể:**\n{issue_summary}", "tag": "lark_md"}},
                    {"tag": "hr"},
    
                ]
            }
        }
        
        response = requests.post(LARK_WEBHOOK_URL, json=payload)
        
        response.raise_for_status()  # Dòng này sẽ báo lỗi nếu status code là 4xx hoặc 5xx
        
        response_json = response.json()
        if response_json.get("StatusCode") == 0:
            logger.success("Gửi thông báo đến Lark thành công!")
            return "Thông báo đã được gửi thành công đến đội ngũ CSKH trên Lark."
        else:
            # Ghi lại lỗi chi tiết từ Lark
            logger.error(f"Lark API trả về lỗi: {response_json.get('msg')}")
            return f"Gửi thông báo Lark thất bại: {response_json.get('msg')}"
            
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Lỗi HTTP khi gọi Lark Webhook: {http_err} - {response.text}")
        return f"Lỗi HTTP khi gửi thông báo Lark: {http_err}"
    except Exception as e:
        logger.error(f"Lỗi không xác định khi gửi thông báo Lark: {e}")
        return f"Lỗi không xác định khi gửi thông báo Lark: {str(e)}"