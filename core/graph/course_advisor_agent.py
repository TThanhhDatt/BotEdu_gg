from langgraph.types import Command
from core.graph.state import AgentState
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.tools import course_toolbox
from database.connection import specialist_llm 

from log.logger_config import setup_logging

logger = setup_logging(__name__)

class CourseAdvisorAgent:
    def __init__(self):
        with open("core/prompts/course_advisor_agent_prompt.md", "r", encoding="utf-8") as f:
            system_prompt = f.read()
            
        context = """
        Các thông tin bạn nhận được:
        - Tên của khách hàng customer_name: {name}
        - Các sản phẩm khách đã xem seen_products: {seen_products}
        """

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt + context),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        self.agent = create_react_agent(
            model=specialist_llm,
            tools=course_toolbox,
            prompt=self.prompt,
            state_schema=AgentState
        )

    def course_advisor_agent_node(self, state: AgentState) -> Command:
        """
        Xử lý các yêu cầu liên quan đến khóa học bằng công cụ `course_toolbox`.

        Args:
            state (AgentState): Trạng thái hội thoại hiện tại.

        Returns:
            Command: Lệnh cập nhật `messages`, `seen_products` (nếu có) và kết thúc luồng.
        """
        try:
            result = self.agent.invoke(state)
            content = result["messages"][-1].content
            
            update = {
                "messages": [AIMessage(content=content, name="course_advisor_agent")],
                "next": "__end__"
            }
            
            if result.get("seen_products", None) is not None:
                    update["seen_products"] = result["seen_products"]
                            
            return Command(
                update=update,
                goto="__end__"
            )
            
        except Exception as e:
            logger.error(f"Lỗi: {e}")
            raise