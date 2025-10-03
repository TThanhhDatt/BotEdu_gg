# core/graph/escalation_agent.py
from langgraph.types import Command
from langchain_core.messages import AIMessage
from core.graph.state import AgentState
from core.tools.notification_tool import send_cskh_notification_tool
from core.utils.save_complaint import save_complaint_to_db 
from core.tools.email_tool import send_escalation_email_tool
from connection.google_connect import SheetLogger
from database.connection import summarization_llm
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
import os
from dotenv import load_dotenv
import logging
load_dotenv()
# Khởi tạo logger cho Google Sheets
sheet_logger = SheetLogger()

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _get_chat_histories(chat_histories: list) -> list:
    formatted_histories = []
    for message in chat_histories:
        formatted_histories.append({
            "type": message.type,
            "content": message.content
        })
    
    return formatted_histories

class EscalationAgent:
    def escalate_node(self, state: AgentState) -> Command:
        customer_name = state.get("name")
        customer_phone = state.get("phone_number")
        user_input = state.get("user_input")
        chat_history = state.get("messages", [])
        
        # 1. Tạo chuỗi hội thoại để làm ngữ cảnh
        history_str = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history])

        # 2. Tạo prompt và gọi LLM tóm tắt
        prompt = [
            SystemMessage(content="You are an expert in customer support. Summarize the following conversation into a professional and concise issue summary in Vietnamese. Focus on the main problem and the customer's request."),
            HumanMessage(content=f"Here is the conversation history:\n{history_str}\n\nLast user message: {user_input}")
        ]
        summary_response = summarization_llm.invoke(prompt)
        issue_summary = summary_response.content
        
        # 1. Lưu lại toàn bộ thông tin cuộc trò chuyện
        save_complaint_to_db(state)

        # Log to Google Sheet
        try:
            sheet_logger.log(
                customer_id=str(state.get("student_id")) if state.get("student_id") else "",
                chat_id=state.get("chat_id"),
                name=customer_name,
                phone=customer_phone,
                chat_histories=_get_chat_histories(state.get("messages")),
                summary=user_input,
                type="Escalation",
                appointment_id=None,
                priority="High",
                platform="Chatbot"
            )
        except Exception as e:
            # You can add more robust error handling here, like logging to a local file
            print(f"Error logging to Google Sheet: {e}")

        # 2. Tạo URL lịch sử chat
        chat_history_url = "https://docs.google.com/spreadsheets/d/1elhqTIxd9T-ZkXIsw5_I3HiMybHW3mYgcmBrGxgnFoM/edit?usp=sharing"

        # 3. Gọi tool để gửi thông báo
        send_cskh_notification_tool.invoke({
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "issue_summary": issue_summary,
            "chat_history_url": chat_history_url
        })
        
        # Gửi email thông báo nếu có cấu hình
        # logger.info("Đang gửi email thông báo cho nhân viên...")
        # email_recipient = os.getenv("RECIPIENT_EMAIL")
        # if email_recipient:
        #     send_escalation_email_tool.invoke({
        #         "recipient_email": email_recipient,
        #         "customer_name": customer_name,
        #         "customer_phone": customer_phone,
        #         "issue_summary": issue_summary
        #     })
        # else:
        #     logger.warning("RECIPIENT_EMAIL chưa được cấu hình, bỏ qua bước gửi mail.")
        # # 4. Tạo phản hồi cho khách hàng
        if "công ty" in user_input.lower() or "doanh nghiệp" in user_input.lower():
             response_message = "Dạ cảm ơn anh/chị. Với nhu cầu đào tạo cho doanh nghiệp, em đã chuyển yêu cầu của anh/chị đến bộ phận chuyên trách. Chuyên viên sẽ liên hệ với mình trong vòng 30 phút nữa ạ."
        else:
            response_message = "Dạ em rất hiểu băn khoăn của anh/chị. Em xin phép ghi nhận và kết nối mình với chuyên viên cấp cao để giải đáp chi tiết hơn. Chuyên viên sẽ sớm liên hệ với mình ạ."
        
        return Command(
            update={
                "messages": [AIMessage(content=response_message, name="escalation_agent")],
                "next": "__end__" 
            },
            goto="__end__"
        )