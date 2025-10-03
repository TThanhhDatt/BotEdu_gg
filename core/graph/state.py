from langgraph.graph.message import add_messages
from datetime import datetime
from typing import Annotated, Any, TypedDict, Optional
from langgraph.prebuilt.chat_agent_executor import AgentState as Origin_AgentState

def _remain_dict(old: dict, new: dict | None):
    return new if new is not None else old

def _remain_value(old: Optional[Any], new: Optional[Any]) -> Optional[Any]:
    return new if new is not None else old

# --- BẮT ĐẦU THAY ĐỔI: Đồng bộ với tên cột database ---
class SeenProducts(TypedDict):
    course_id: int
    name: str
    description: str
    type: str
    duration: int
    price: int
    sessions_per_week: int
    minutes_per_session: int
    instructor_name: str
    
class Cart(TypedDict):
    course_id: int # Đổi từ product_des_id
    price: int
    subtotal: int

class OrderItem(TypedDict):
    item_id: int
    course_id: int # Đổi từ product_des_id
    name: str      # Đổi từ product_name
    description: str
    type: str
    duration: int
    price: int
    sessions_per_week: int
    minutes_per_session: int
    instructor_name: str
# --- KẾT THÚC THAY ĐỔI ---
    
class Order(TypedDict):
    order_id: int
    status: str
    payment: str
    order_total: int
    discount_voucher: int
    grand_total: int
    created_at: datetime
    receiver_name: str
    receiver_phone_number: str
    receiver_email: str
    items: dict[int, OrderItem]
    admission_day: Optional[str]

class AgentState(Origin_AgentState):
    messages: Annotated[list, add_messages]
    user_input: Annotated[str, _remain_value]
    chat_id: Annotated[str, _remain_value]
    next: Annotated[str, _remain_value]
    student_id: Annotated[Optional[int], _remain_value]
    name: Annotated[Optional[str], _remain_value]
    phone_number: Annotated[Optional[str], _remain_value]
    email: Annotated[Optional[str], _remain_value]
    payment: Annotated[Optional[str], _remain_value]
    seen_products: Annotated[Optional[dict[int, SeenProducts]], _remain_dict]
    cart: Annotated[Optional[dict[int, Cart]], _remain_dict]
    order: Annotated[Optional[dict[int, Order]], _remain_dict]
    
def init_state() -> AgentState:
    return AgentState(
        messages=[],
        user_input="",
        chat_id="",
        next="",
        student_id=None,
        name=None,
        phone_number=None,
        email=None,
        payment=None,
        seen_products=None,
        cart=None,
        order=None
    )