from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

import json
from typing import Annotated, Optional, List
import re
from core.utils.tool_function import build_update
from core.graph.state import AgentState, SeenProducts
from database.connection import supabase_client, embeddings_model

from log.logger_config import setup_logging

logger = setup_logging(__name__)

def parse_custom_string_to_dict(content: str) -> dict:
    """
    Phân tích một chuỗi có định dạng "key: value, key: value,..." thành một dictionary.
    Hàm này được thiết kế để xử lý chuỗi không phải là JSON hợp lệ.
    """
    if not content or not isinstance(content, str):
        return {}
    
    # Tách các cặp key-value bằng cách tìm các key đã biết
    keys = [
        "course_id", "name", "description", "type", "duration", "price", 
        "sessions_per_week", "minutes_per_session", "instructor_name"
    ]
    
    # Tạo một pattern regex để tìm key theo sau là dấu hai chấm
    pattern = re.compile(f"({'|'.join(keys)}):")
    
    # Tách chuỗi dựa trên các key tìm thấy
    parts = pattern.split(content)[1:]
    
    if not parts:
        return {}
        
    data = {}
    # Lặp qua các cặp key-value
    for i in range(0, len(parts), 2):
        key = parts[i].strip()
        # Lấy giá trị là phần chuỗi giữa key hiện tại và key tiếp theo
        value = parts[i+1].strip()
        
        # Loại bỏ dấu phẩy ở cuối nếu có
        if i + 2 < len(parts):
            next_key_index = value.rfind(parts[i+2])
            if next_key_index != -1:
                value = value[:next_key_index].strip()
        if value.endswith(','):
            value = value[:-1].strip()
            
        # Chuyển đổi các giá trị số
        if key in ["course_id", "duration", "price", "sessions_per_week", "minutes_per_session"]:
            try:
                data[key] = int(value)
            except ValueError:
                data[key] = value
        else:
            data[key] = value
            
    return data

def _update_seen_products(
    seen_products: dict, 
    products: List[dict]
) -> dict:
    """
    Cập nhật `seen_products` trong state bằng kết quả khóa học trả về.
    """
    for prod in products:
        course_id = prod.get("course_id")
        
        seen_products[course_id] = SeenProducts(
            course_id=course_id,
            name=prod.get("name"),
            description=prod.get("description"),
            type=prod.get("type"),
            duration=prod.get("duration"), 
            price=prod.get("price"),
            sessions_per_week=prod.get("sessions_per_week"),
            minutes_per_session=prod.get("minutes_per_session"),
            instructor_name=prod.get("instructor_name")
        )
        # --- KẾT THÚC THAY ĐỔI ---
    return seen_products

@tool
def get_courses_tool(
    keywords: Annotated[str, "Từ khóa tìm kiếm khóa học mà nguời dùng cung cấp"],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Công cụ này ưu tiên tìm kiếm chính xác bằng SQL nếu người dùng cung cấp ID hoặc tên khóa học. 
    Nếu không, nó sẽ sử dụng tìm kiếm ngữ nghĩa (RAG) để xử lý các câu hỏi chung chung về khóa học.

    Chức năng: Tìm kiếm thông tin khóa học. 

    Tham số: 
        - keywords (str): chỉ chứa phần từ khoá cốt lõi là tên hoặc mô tả chính xác của khóa học mà người dùng quan tâm.
    """
    logger.info(f"get_courses_tool được gọi với keywords: {keywords}")
    # --- SQL First Approach ---
    try:
        response = (
            supabase_client.from_("courses_description").select("*")
            .ilike('name', f'%{keywords}%')
            .limit(5).execute()
        )
     
        db_result = response.data

        if db_result:
            logger.info("Có dữ liệu trả về từ SQL")
            
            updated_seen_products = _update_seen_products(
                seen_products=state["seen_products"] if state["seen_products"] is not None else {},
                products=db_result
            )
            
            courses_summary = []
            for course in db_result:
                courses_summary.append(
                    f"- {course.get('name')}: {course.get('description')}"
                )
            
            formatted_response = (
                "Đây là các khóa học tìm thấy dựa trên yêu cầu của bạn:\n"
                f"{' '.join(courses_summary)}\n\n"
                "Em sẽ tóm gọn lại thông tin khóa học một cách ngắn gọn và dễ hiểu nhé.\n"
            )
            
            if state.get("phone_number"):
                formatted_response += "Anh/chị có muốn đăng ký khóa học nào không ạ?"
            else:
                formatted_response += "Để tiện tư vấn đăng ký, anh/chị có thể cho em xin số điện thoại được không ạ?"
            
            logger.info("Trả về kết quả từ SQL")
            return Command(
                update=build_update(
                    content=formatted_response,
                    tool_call_id=tool_call_id,
                    seen_products=updated_seen_products
                )
            )
            
        logger.info("Không có kết quả từ SQL, chuyển sang tìm kiếm RAG")
        query = f"{state["user_input"]}. {keywords}"
        query_embedding = embeddings_model.embed_query(query)
        
        response = supabase_client.rpc(
            "match_courses",
            {
                "query_embedding": query_embedding,
                "match_count": 5,
                "filter": {}
            }
        ).execute()

        rag_results = response.data
        
        if not rag_results:
            logger.info("Không có kết quả từ RAG")
            return Command(update=build_update(
                content="Xin lỗi, em không tìm thấy thông tin nào liên quan đến câu hỏi của anh/chị.",
                tool_call_id=tool_call_id
            ))

        logger.info("Có kết quả trả về từ RAG")
        products = []
        for item in rag_results:
            content = item.get("content")
            if content and isinstance(content, str):
                # Sử dụng hàm parse_custom_string_to_dict thay vì json.loads
                parsed_data = parse_custom_string_to_dict(content)
                if parsed_data:
                    products.append(parsed_data)
                else:
                    logger.warning(f"Bỏ qua content không thể phân tích từ RAG: {content}")
        
        if not products:
            logger.info("Không thể parse sản phẩm từ kết quả RAG")
            return Command(update=build_update(
                content="Xin lỗi, em không thể xác định được thông tin khóa học từ kết quả tìm kiếm.",
                tool_call_id=tool_call_id
            ))

        
        updated_seen_products = _update_seen_products(
            seen_products=state["seen_products"] if state["seen_products"] is not None else {}, 
            products=products
        )
        
        courses_summary_rag = []
        for course in products:
            courses_summary_rag.append(
                f"- {course.get('name')}: {course.get('description')}"
            )
        
        formatted_response = (
            "Dưới đây là các khóa học phù hợp với yêu cầu của anh/chị ạ:\n\n"
            f"{' '.join(courses_summary_rag)}\n"
            "Em sẽ tóm tắt ngắn gọn để anh/chị dễ nắm thông tin nhé."
        )
        
        logger.info("Trả về kết quả từ RAG")
        return Command(
            update=build_update(
                content=formatted_response,
                tool_call_id=tool_call_id,
                seen_products=updated_seen_products
            )
        )

    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def get_schedule_tool(
    course_id: Annotated[int, "ID của khóa học cần truy vấn lịch học."],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này để truy vấn lịch học chi tiết của một khóa học dựa vào course_id.
    """
    logger.info(f"get_schedule_tool được gọi với course_id: {course_id}")
    
    if not course_id:
        return Command(update=build_update(
            content="Không xác định được khóa học, hãy hỏi lại khách hàng xem họ muốn xem lịch học của khóa nào.",
            tool_call_id=tool_call_id
        ))

    try:
        response = (
            supabase_client.table("schedules")
            .select("*")
            .eq("course_id", course_id)
            .execute()
        )
        
        schedules = response.data
        
        if not schedules:
            return Command(update=build_update(
                content=f"Xin lỗi, hiện tại chưa có lịch học cho khóa học này. Em sẽ cập nhật sớm nhất ạ.",
                tool_call_id=tool_call_id
            ))

        formatted_schedules = ""
        for i, schedule in enumerate(schedules):
            start_date = schedule.get('start_date')
            end_date = schedule.get('end_date')
            days_of_week = schedule.get('days_of_week')
            time = schedule.get('time')
            mode = schedule.get('mode')
            location_link = schedule.get('location_link')

            formatted_schedules += (
                f"Lịch học {i+1}:\n"
                f"- Hình thức: {mode}\n"
                f"- Thời gian: {time}, các ngày {days_of_week}\n"
                f"- Khai giảng: {start_date}\n"
                f"- Kết thúc: {end_date}\n"
                f"- Địa điểm/Link học: {location_link}\n\n"
            )

        return Command(update=build_update(
            content=f"Dạ, đây là lịch học chi tiết của khóa học ạ:\n\n{formatted_schedules}",
            tool_call_id=tool_call_id
        ))

    except Exception as e:
        logger.error(f"Lỗi khi truy vấn lịch học: {e}")
        return Command(update=build_update(
            content="Đã có lỗi xảy ra khi em tra cứu lịch học, anh/chị vui lòng thử lại sau nhé.",
            tool_call_id=tool_call_id
        ))

@tool
def get_qna_tool(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này cho các câu hỏi về thắc mắc về khóa học, nội dung khóa học. 
    Công cụ sẽ tìm kiếm trong cơ sở dữ liệu Hỏi & Đáp (Q&A) để cung cấp câu trả lời và hướng dẫn chi tiết.
    """
    query = state["user_input"]
    logger.info(f"get_qna_tool được gọi với query: {query}")
    all_documents = []
    
    try:
        query_embedding = embeddings_model.embed_query(query)

        response = supabase_client.rpc(
            "match_qna",
            {
                "query_embedding": query_embedding,
                "match_count": 3,
                "filter": {}
            }
        ).execute()

        if not response.data:   # ✅ sửa lại check lỗi
            logger.warning("Không có dữ liệu trả về từ RPC match_qna")
            return Command(
                update=build_update(
                    content="Xin lỗi, em không tìm thấy thông tin nào liên quan đến câu hỏi của anh/chị.",
                    tool_call_id=tool_call_id
                )
            )

        for item in response.data:
            all_documents.append(item.get("content", ""))
        
        logger.info(f"Tìm thấy {len(all_documents)} tài liệu Q&A")
        return Command(
            update=build_update(
                content=f"Đây là các thông tin tôi tìm thấy liên quan đến câu hỏi của bạn: {all_documents}",
                tool_call_id=tool_call_id
            )
        )
             
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def get_promotions_tool(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này để tìm tất cả các khóa học đang có chương trình khuyến mãi hoặc giảm giá.
    Gọi tool này khi người dùng hỏi về "ưu đãi", "khuyến mãi", "giảm giá", "sale".
    """
    logger.info("get_promotions_tool được gọi")
    try:
        response = (
            supabase_client.from_("courses_description")
            .select("course_id, name, price, promotion")
            .gt("promotion", 0)  # Lấy các khóa có promotion > 0
            .limit(10)
            .execute()
        )

        promotional_courses = response.data
        if not promotional_courses:
            logger.info("Không tìm thấy khóa học nào có khuyến mãi.")
            return Command(update=build_update(
                content="Dạ hiện tại trung tâm chưa có chương trình ưu đãi đặc biệt nào ạ. Tuy nhiên, anh/chị có thể tham khảo các khóa học chất lượng cao của bên em nhé.",
                tool_call_id=tool_call_id
            ))

        # Lấy thông tin chi tiết của các khóa học có khuyến mãi để cập nhật state
        full_details_ids = [course['course_id'] for course in promotional_courses]
        full_details_res = supabase_client.from_("courses_description").select("*").in_("course_id", full_details_ids).execute()
        
        updated_seen_products = _update_seen_products(
            seen_products=(state.get("seen_products") or {}).copy(),
            products=full_details_res.data
        )

        # Tạo chuỗi phản hồi cho người dùng
        response_lines = ["Dạ hiện tại trung tâm đang có các ưu đãi hấp dẫn cho những khóa học sau ạ:"]
        for course in promotional_courses:
            original_price = course.get("price", 0)
            promotion_rate = course.get("promotion", 0.0)
            discounted_price = original_price * (1 - promotion_rate)
            response_lines.append(
                f"- Khóa học '{course.get('name')}': Giảm {promotion_rate:.0%}, "
                f"giá gốc {original_price:,.0f} VNĐ chỉ còn **{discounted_price:,.0f} VNĐ**."
            )
        
        response_lines.append("\nAnh/chị quan tâm đến khóa học nào để em tư vấn chi tiết hơn ạ?")
        formatted_response = "\n".join(response_lines)
        
        logger.info(f"Tìm thấy {len(promotional_courses)} khóa học có khuyến mãi.")
        return Command(
            update=build_update(
                content=formatted_response,
                tool_call_id=tool_call_id,
                seen_products=updated_seen_products
            )
        )

    except Exception as e:
        logger.error(f"Lỗi khi truy vấn khuyến mãi: {e}")
        return Command(update=build_update(
            content="Đã có lỗi xảy ra khi em tra cứu thông tin ưu đãi, anh/chị vui lòng thử lại sau nhé.",
            tool_call_id=tool_call_id
        ))