from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.tools import enrollment_toolbox
from core.graph.state import AgentState
from database.connection import specialist_llm

from log.logger_config import setup_logging

logger = setup_logging(__name__)


class EnrollmentAgent:
    def __init__(self):
        with open("core/prompts/enrollment_agent_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = """
        Các thông tin bạn nhận được:
        - Tên của khách hàng customer_name: {name}
        - SĐT của khách phone_number: {phone_number}
        - Email của khách: {email}
        - Các sản phẩm khách đã xem seen_products: {seen_products}
        - Giỏ hàng của khách: {cart}
        - Phương thức thanh toán đã chọn payment: {payment}
        """
            
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        self.agent = create_react_agent(
            model=specialist_llm,
            tools=enrollment_toolbox,
            prompt=self.prompt,
            state_schema=AgentState
        )
    
    def enrollment_agent_node(self, state: AgentState) -> Command:
        """
        Xử lý các yêu cầu liên quan đến đơn hàng (lên đơn, ....) bằng `enrollment_toolbox`.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, các trường trạng thái (`order`, `cart`, ... nếu có) và kết thúc luồng.
        """
        try:
            result = self.agent.invoke(state)
            content = result["messages"][-1].content
            
            update = {
                "messages": [AIMessage(content=content, name="enrollment_agent")],
                "next": "__end__"
            }
            
            for key in ([
                "student_id", "name", "phone_number", "email", 
                "payment", "seen_products", "cart", "order"
            ]):
                if result.get(key, None) is not None:
                    update[key] = result[key]
            
            return Command(
                update=update,
                goto="__end__"
            )
            
        except Exception as e:
            logger.error(f"Lỗi: {e}")
            raise