# Thêm import cho END từ langgraph.graph
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from core.graph.state import AgentState
from core.graph.supervisor import Supervisor
# Sửa lại các đường dẫn import cho gọn gàng và chính xác
from core.graph.enrollment_agent import EnrollmentAgent
from core.graph.course_advisor_agent import CourseAdvisorAgent
from core.graph.modify_agent import ModifyAgent
from core.graph.escalation_agent import EscalationAgent

def create_main_graph() -> StateGraph:
    # Khởi tạo các agent
    course_advisor_agent = CourseAdvisorAgent()
    enrollment_agent = EnrollmentAgent()
    modify_agent = ModifyAgent()
    supervisor_chain = Supervisor()
    escalation_agent = EscalationAgent()
    
    # Xây dựng graph
    workflow = StateGraph(AgentState)
    workflow.add_node(
        "supervisor", 
        supervisor_chain.supervisor_node,
    )
    
    workflow.add_node(
        "course_advisor_agent", 
        # Sửa lại tên hàm cho nhất quán
        course_advisor_agent.course_advisor_agent_node, 
    )
    workflow.add_node(
        "enrollment_agent", 
        # Sửa lại tên hàm cho nhất quán
        enrollment_agent.enrollment_agent_node,
    )
    workflow.add_node(
        "modify_agent", 
        modify_agent.modify_agent_node,
    )
    workflow.add_node(
        "escalation_agent", 
        escalation_agent.escalate_node
    )
    
    workflow.set_entry_point("supervisor")

    # --- BẮT ĐẦU PHẦN THÊM MỚI ---
    
    # 1. Định nghĩa hàm định tuyến
    # Hàm này sẽ đọc giá trị "next" từ state mà supervisor đã quyết định
    def route(state: AgentState) -> str:
        return state["next"]

    # 2. Thêm các cạnh điều kiện
    # Dòng này nói với workflow: "Sau khi chạy node 'supervisor', hãy gọi hàm 'route'.
    # Dựa trên kết quả trả về của hàm 'route', hãy đi đến node tương ứng trong map dưới đây."
    workflow.add_conditional_edges(
        "supervisor",
        route,
        {
            # Nếu supervisor quyết định là 'course_advisor_agent', đi đến node 'product_agent'
            "course_advisor_agent": "course_advisor_agent",
            # Nếu supervisor quyết định là 'enrollment_agent', đi đến node 'order_agent'
            "enrollment_agent": "enrollment_agent",
            # Nếu supervisor quyết định là 'modify_agent', đi đến node 'modify_order_agent'
            "modify_agent": "modify_agent",
            "escalation_agent": "escalation_agent",
            # Nếu supervisor quyết định kết thúc, đi đến END
            "__end__": END
        }
    )

    # Thêm cạnh để sau khi các agent chạy xong thì quay về supervisor hoặc kết thúc
    # Ở đây, logic của bạn là mỗi agent chạy xong sẽ tự kết thúc (__end__)
    # nên không cần thêm cạnh quay về supervisor. Nếu muốn agent chạy xong lại
    # quay về supervisor, bạn sẽ thêm dòng:
    # workflow.add_edge("product_agent", "supervisor")
    # workflow.add_edge("order_agent", "supervisor")
    # workflow.add_edge("modify_order_agent", "supervisor")

    # --- KẾT THÚC PHẦN THÊM MỚI ---

    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)
    
    return graph