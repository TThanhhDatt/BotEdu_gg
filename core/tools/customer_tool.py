from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

from typing import Annotated, Optional

from core.graph.state import AgentState
from database.connection import supabase_client
from core.utils.tool_function import build_update

from log.logger_config import setup_logging

logger = setup_logging(__name__)

@tool
def modify_customer_tool(
    new_phone: Annotated[Optional[str], "Số điện thoại khách muốn thêm vào hoặc cập nhật"],
    new_name: Annotated[Optional[str], "Tên khách muốn thêm vào hoặc cập nhật"],
    new_email: Annotated[Optional[str], "Email khách muốn thêm vào hoặc cập nhật"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này để chỉnh sửa thông tin của khách hàng.

    Chức năng: Chỉnh sửa thông tin (tên, số điện thoại, email) cho một khách hàng đã tồn tại trong hệ thống.

    Tham số:
        - new_phone (str): Số điện thoại mới của khách hàng. Dùng để xác định và cập nhật thông tin.
        - new_name (str, tùy chọn): Tên mới của khách hàng.
        - new_email (str, tùy chọn): Email mới của khách hàng.
    """
    logger.info("modify_customer_tool được gọi")
    
    if not any([new_name, new_email, new_phone]):
        logger.info(f"Khách thiếu ít nhất 1 thông tin Tên: {new_name} | Email: {new_email} | Số điện thoại: {new_phone}")
        return Command(
            update=build_update(
                content="Khách phải cung cấp ít nhất một thông tin liên quan đến tên, email với số điện thoại để cập nhật, hỏi khách",
                tool_call_id=tool_call_id
            )
        )

    try:
        logger.info("Kiểm tra khách hàng")
        check_customer_exist = (
            supabase_client.table('students')
            .select('student_id')
            .eq("student_id", state["student_id"])
            .execute()
        )
        
        # Nếu khách không tồn tại -> thông báo
        if not check_customer_exist.data:
            logger.error("Lỗi không tìm thấy khách hàng")
            return Command(
                update=build_update(
                    content=f"Không tìm thấy khách hàng, xin lỗi khách",
                    tool_call_id=tool_call_id
                )
            )

        logger.info("Thấy thông tin khách hàng")
        update_payload = {}
        if new_name:
            update_payload['name'] = new_name
        if new_phone:
            update_payload['phone_number'] = new_phone
        if new_email:
            update_payload['email'] = new_email

        logger.info(f"Cập nhật thông tin khách tên: {new_name} | SĐT: {new_phone} | địa chỉ: {new_email}")
        response = (
            supabase_client.table('students')
            .update(update_payload)
            .eq('student_id', state["student_id"])
            .execute()
        )
        updated_info = response.data[0]
        
        if not updated_info:
            logger.error("Xảy ra lỗi ở cấp DB -> Không thể cập nhật khách")
            return Command(
                update=build_update(
                    content=(
                        "Có lỗi trong quá trình thể cập nhật "
                        f"thông tin cho khách hàng có ID {state["student_id"]}"
                    ),
                    tool_call_id=tool_call_id
                )
            )
        
        logger.info("Cập nhật thông tin khách thành công")
        return Command(
            update=build_update(
                content=(
                    "Đã cập nhật thông tin học viên thành công:\n"
                    f"- Tên học viên: {updated_info["name"]}\n"
                    f"- Số điện thoại học viên {updated_info["phone_number"]}\n"
                    f"- Email học viên: {updated_info["email"]}\n"
                    "Nếu học viên đang trong quá trình lên đơn thì bạn hãy "
                    "hỏi là học viên có muốn lên đơn luôn không."
                ),
                tool_call_id=tool_call_id,
                name=updated_info["name"],
                phone_number=updated_info["phone_number"],
                email=updated_info["email"],
            )
        )

    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise
    