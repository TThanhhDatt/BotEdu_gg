from langgraph.types import Command
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.graph.state import AgentState
from core.tools import modify_toolbox
from database.connection import specialist_llm

from log.logger_config import setup_logging

logger = setup_logging(__name__)


class ModifyAgent:
    def __init__(self):
        with open("core/prompts/modify_agent_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
        
        context = """
        Các thông tin bạn nhận được:
        - Tên của khách hàng customer_name: {name}
        - SĐT của khách phone_number: {phone_number}
        - Email của khách: {email}
        - Các sản phẩm khách đã xem seen_products: {seen_products}
        - Đơn hàng của khách: {order}
        """    
         
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        self.agent = create_react_agent(
            model=specialist_llm,
            tools=modify_toolbox,
            prompt=self.prompt,
            state_schema=AgentState
        )
    
    def modify_agent_node(self, state: AgentState) -> Command:
        """
        Xử lý các yêu cầu chỉnh sửa đơn hàng: thay đổi người nhận, thay đổi/xóa sản phẩm,
        hủy đơn... bằng `modify_toolbox`.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, `order`, và điều hướng kết thúc luồng.
        """
        try:
            state["messages"].append(
                HumanMessage(content=(
                        "Đây là các thông tin bạn nhận được:\n"
                        f"- seen_products: {state["seen_products"]}\n"
                        f"- order: {state["order"]}\n" 
                        f"- name: {state["name"]}\n"
                        f"- phone_number: {state["phone_number"]}\n"
                        f"- email: {state["email"]}\n"
                        "Hãy dựa vào đây là quyết định gọi "
                        "tool hay không."            
                    )
                )
            )
            result = self.agent.invoke(state)
            content = result["messages"][-1].content
            
            update = {
                "messages": [AIMessage(content=content, name="modify_agent")],
                "next": "__end__"
            }
            
            for key in ["student_id", "name", "phone_number", "email", "seen_products", "order"]:
                if result.get(key, None) is not None:
                    update[key] = result[key]
            
            return Command(
                update=update,
                goto="__end__"
            )
            
        except Exception as e:
            logger.error(f"Lỗi: {e}")
            raise