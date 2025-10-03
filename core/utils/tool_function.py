from langgraph.types import Command
from langchain_core.messages import ToolMessage

from typing import Any
from langgraph.graph import StateGraph
from core.graph.state import AgentState


def build_update(
    content: str,
    tool_call_id: Any,
    **kwargs
) -> dict:
    """
    Tạo payload `update` chuẩn cho LangGraph `Command` với một `ToolMessage`.

    Args:
        content (str): Nội dung phản hồi hiển thị cho người dùng.
        tool_call_id (Any): ID gọi tool để liên kết message với lần gọi công cụ.
        **kwargs: Các trường trạng thái bổ sung để cập nhật vào state.

    Returns:
        dict: Payload cập nhật cho `Command(update=...)`.
    """
    return {
        "messages": [
            ToolMessage
            (
                content=content,
                tool_call_id=tool_call_id
            )
        ],
        **kwargs
    }
    
def fail_if_missing(condition, message, tool_call_id) -> Command:
    """
    Trả về `Command` chứa thông báo hướng dẫn nếu điều kiện tiền đề không thỏa.

    Args:
        condition (Any): Điều kiện cần thỏa để tiếp tục xử lý.
        message (str): Nội dung hướng dẫn/nhắc người dùng bổ sung.
        tool_call_id (Any): ID gọi tool hiện tại.

    Returns:
        Command: Cập nhật message nếu thiếu điều kiện, ngược lại trả None (fallthrough).
    """
    if not condition:
        return Command(
            update=build_update(
                content=message,
                tool_call_id=tool_call_id,
            )
        )
        
async def test_bot(
    graph: StateGraph,
    state: AgentState,
    config: dict,
    mode: str = "updates"
):
    async for data in graph.astream(state, subgraphs=True, config=config, mode=mode):
        for key, value in data[1].items():
            if "messages" in value and value["messages"]:
                print(value["messages"][-1].pretty_print())