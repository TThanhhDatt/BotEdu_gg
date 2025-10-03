from langgraph.types import Command
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.graph.state import AgentState 
from database.connection import supabase_client
from database.connection import orchestrator_llm

from log.logger_config import setup_logging

logger = setup_logging(__name__)

class Route(BaseModel):
    """Chọn agent tiếp theo để xử lý yêu cầu."""
    next: Literal["course_advisor_agent", "enrollment_agent", "modify_agent", "escalation_agent", "__end__"] = Field(
        description=(
            "Lựa chọn PHẢI DỰA TRÊN QUY TẮC ƯU TIÊN. "
            "Chọn 'escalation_agent' cho các yêu cầu B2B hoặc khiếu nại. "
            "Sau đó mới xét đến 'course_advisor_agent', 'enrollment_agent', 'modify_agent'. "
            "Chọn '__end__' để kết thúc."
        )
    )
    
    final_response: Optional[str] = Field(
        default=None,
        description="Nếu 'next' là '__end__', hãy tạo một lời chào kết thúc ngắn gọn, lịch sự bằng tiếng Việt. Ví dụ: 'Cảm ơn anh/chị đã quan tâm ạ. Nếu cần hỗ trợ thêm, anh/chị cứ liên hệ lại với em nhé!'. Nếu cuộc trò chuyện kết thúc vì một lý do khác (ví dụ: yêu cầu không phù hợp), hãy đưa ra một phản hồi chuyên nghiệp tương ứng."
    )

def _get_or_create_customer(chat_id: str) -> Optional[dict]:
    response = (
        supabase_client.table("students")
        .upsert(
            {"chat_id": chat_id},
            on_conflict="chat_id"
        )
        .execute()
    )
    
    logger.info(f"Tạo mới hoặc lấy thông tin khách: {response.data[0]}")
    
    return response.data[0] if response.data else None

class Supervisor:
    def __init__(self):
        with open("core/prompts/supervisor_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = (
            "Các thông tin bạn nhận được:\n"
            "- Đơn hàng của khách: {order}\n"
            "- Giỏ hàng của khách: {cart}"
        )
            
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages"),
            ("human", "{user_input}")
        ])
        
        self.chain = self.prompt | orchestrator_llm.with_structured_output(Route)
        
    def supervisor_node(self, state: AgentState) -> Command:
        """
        Phân luồng yêu cầu của khách tới agent phù hợp dựa trên `state` và prompt điều phối.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, trường `next` và điều hướng `goto` tới node tiếp theo.
        """
        update = {}
        try:
            if not state["student_id"]:
                customer = _get_or_create_customer(chat_id=state["chat_id"])

                if not customer:
                    logger.error("Lỗi không lấy được thông tin khách")
                else:
                    update.update({
                        "student_id": customer.get("student_id"),
                        "name": customer.get("name"),
                        "phone_number": customer.get("phone_number"),
                        "email": customer.get("email")
                    })
            else:
                logger.info(
                    "Thông tin của khách: "
                    f"- Tên: {state["name"]} | "
                    f"- Số điện thoại: {state["phone_number"]} | "
                    f"- Email: {state["email"]}"
                )
            
            logger.info(f"Yêu cầu của khách: {state["user_input"]}")
            
            result = self.chain.invoke(state)
            
            next_node = result.next
            update["next"] = next_node
            if next_node == "__end__":
                # Nếu Supervisor quyết định kết thúc, sử dụng lời chào do LLM tạo ra
                final_message = result.final_response or "Cảm ơn anh/chị đã quan tâm ạ. Hẹn gặp lại anh/chị sau!"
                update["messages"] = [AIMessage(content=final_message)]
            else:
                # Nếu tiếp tục, chỉ thêm tin nhắn của người dùng như cũ
                update["messages"] = [HumanMessage(content=state["user_input"])]
            
            logger.info(f"Agent tiếp theo: {next_node}")
    
            return Command(
                update=update,
                goto=next_node
            )
        
        except Exception as e:
            logger.error(f"Lỗi: {e}")
            raise
        