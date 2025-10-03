from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import AIMessage
from datetime import datetime, timedelta
from typing import Optional, Annotated

from database.connection import supabase_client
from core.utils.tool_function import build_update
from core.graph.state import AgentState, Order, OrderItem, Cart
from core.tools.notification_tool import send_altercourse_notification_tool
from log.logger_config import setup_logging
from connection.order_connect import OrderSheetLogger 

logger = setup_logging(__name__)

def _get_first_schedule_start_date(course_id: int) -> Optional[str]:
    """
    Lấy ngày khai giảng (start_date) sớm nhất của một khóa học.
    """
    try:
        response = (
            supabase_client.table("schedules")
            .select("start_date")
            .eq("course_id", course_id)
            .order("start_date", desc=False)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0].get("start_date")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi lấy ngày khai giảng: {e}")
        return None

def _get_order_details(order_id: int) -> dict | None:
    """
    Lấy chi tiết một đơn hàng kèm các `order_items` và thông tin sản phẩm liên quan.

    Args:
        order_id (int): Mã đơn hàng cần truy vấn.

    Returns:
        dict | None: Bản ghi đơn hàng và các mục hàng; None nếu không tìm thấy.
    """
    try:
        res = (
            supabase_client.table("orders")
            .select("""
                *, 
                order_items (
                    item_id,
                    course_id,
                    price,
                    subtotal,
                    courses_description (*)
                )
            """)
            .eq("order_id", order_id)
            .single()
            .execute()
        )
        
        return res.data if res.data else None
    except Exception:
        raise
    
def _get_all_editable_orders(student_id: int) -> list[dict] | None:
    """
    Lấy tối đa 5 đơn hàng gần nhất có thể chỉnh sửa (
    loại trừ các trạng thái đã hoàn tất/hủy/trả/refund).

    Args:
        student_id (int): Mã khách hàng.

    Returns:
        list[dict] | None: Danh sách đơn hàng hoặc None nếu không có.
    """
    try:
        forbidden = "(delivered,cancelled,returned,refunded)" ## các trạng thái không thể chỉnh sửa
        query = (
            supabase_client.table("orders")
            .select("""
                *, 
                order_items (
                    item_id,
                    course_id,
                    price,
                    subtotal,
                    courses_description (*
                    )
                )
            """)
            .eq("student_id", student_id)
            .not_.in_("status", forbidden)
            .order("created_at", desc=True)
            .limit(5)
        )
        res = query.execute()
        return res.data if res.data else None
    except Exception:
        raise
    
    
def _format_order_details(
    raw_order_detail: dict
) -> str:
    """
    Định dạng thông tin chi tiết đơn hàng thành chuỗi văn bản thân thiện.

    Args:
        raw_order_detail (dict): Dữ liệu đơn hàng gồm `order_items` và trường thông tin liên quan.

    Returns:
        str: Nội dung mô tả chi tiết đơn hàng.
    """
    order_detail = f"Mã đơn: {raw_order_detail["order_id"]}\n\n"
    index = 1
    for item in raw_order_detail.get("order_items", []):
        prod = item.get("courses_description", {})

        name = prod.get("name", "")
        course_id = prod.get("course_id")
        # description = prod.get("description", "")
        type = prod.get("type", "")
        price = item.get("price", 0)
        sessions_per_week = prod.get("sessions_per_week", 0)
        minutes_per_session = prod.get("minutes_per_session", 0)
        duration = prod.get("duration", 0)
        instructor_name = prod.get("instructor_name", "")
        promotion = prod.get("promotion", 0.0)
        subtotal = item.get("subtotal", 0)
        discounted_price = price * (1 - promotion)        
        order_detail += (
            f"STT: {index}\n"
            f"Mã khóa học: {course_id}.\n"
            f"Tên khóa học: {name}.\n"
            #f"Mô tả: {description}.\n"
            f"Hình thức: {type}.\n"
            f"Thời lượng: {duration} tuần.\n"
            f"Số buổi học mỗi tuần: {sessions_per_week} buổi.\n"
            f"Số phút mỗi buổi học: {minutes_per_session} phút.\n"
            f"Tên giảng viên: {instructor_name}.\n"
            f"Học phí: {price} VNĐ.\n"
            f"Khuyến mãi: {promotion*100:.0f}%.\n"
            f"Học phí cần đóng: {discounted_price:,.0f} VNĐ.\\n" 
            f"Tổng giá: {subtotal} VNĐ.\n\n"
        )

        index += 1
    # format datetime
    dt = datetime.fromisoformat(raw_order_detail["created_at"])
    formatted_date = dt.strftime("%H:%M:%S - %d/%m/%Y")
    
    order_detail += (
        f"Tổng cộng giỏ hàng: {raw_order_detail["order_total"]} VNĐ.\n"
        f"Voucher: {raw_order_detail["discount_voucher"]} VNĐ.\n"
        f"Tổng cộng: {raw_order_detail["grand_total"]} VNĐ.\n"
        f"Phương thức thanh toán: {raw_order_detail["payment"]}.\n\n"
        f"Tên người nhận: {raw_order_detail["receiver_name"]}.\n"
        f"Số điện thoại người nhận: {raw_order_detail["receiver_phone_number"]}.\n"
        f"Email người nhận: {raw_order_detail["receiver_email"]}.\n"
        f"Ngày đặt hàng: {formatted_date}\n\n"
    )
    
    return order_detail
## Stop here
def _return_all_editable_orders(
    student_id: int,
    list_raw_order_detail: Optional[list[dict]] = None
) -> str:
    """
    Trả về chuỗi mô tả danh sách các đơn hàng có thể chỉnh sửa của một khách.

    Args:
        student_id (int): Mã khách hàng.
        list_raw_order_detail (Optional[list[dict]]): Dữ liệu đơn hàng nếu đã có sẵn.

    Returns:
        str: Chuỗi mô tả tổng hợp nhiều đơn hàng.
    """
    try:
        if not list_raw_order_detail:
            list_raw_order_detail = _get_all_editable_orders(
                student_id=student_id
            )
            
            if not list_raw_order_detail:
                return f"Không tìm thấy đơn hàng khách với ID: {student_id}"
            
        
        order_detail = ""
        order_index = 1
        for raw_order in list_raw_order_detail:
            order_detail += (
                f"Đơn thứ: {order_index}\n"
                f"{_format_order_details(
                    raw_order_detail=raw_order
                )}"
            )
            
            order_index += 1
        
        return order_detail
        
    except Exception as e:
        raise

def _return_order_details(
    order_id: int,
    raw_order_detail: Optional[dict] = None
) -> str:
    """
    Trả về mô tả chi tiết cho một đơn hàng theo `order_id`.

    Args:
        order_id (int): Mã đơn.
        raw_order_detail (Optional[dict]): Dữ liệu nếu đã có sẵn, tránh query lại.

    Returns:
        str: Chuỗi mô tả chi tiết đơn hàng.
    """
    try:
        if not raw_order_detail:
            raw_order_detail = _get_order_details(order_id=order_id)
            
            if not raw_order_detail:
                return f"Không tìm thấy đơn hàng với ID {order_id}"

        return _format_order_details(raw_order_detail=raw_order_detail)
    except Exception as e:
        raise


def _update_order_state(order: dict) -> dict:
    """
    Chuyển dữ liệu thô từ DB thành cấu trúc `Order` dùng trong `AgentState`.

    Args:
        order (dict): Dữ liệu đơn hàng bao gồm danh sách item và thông tin người nhận.

    Returns:
        dict: Cấu trúc `Order` sẵn sàng lưu vào state.
    """
    items_list: dict[int, OrderItem] = {}
    
    for ot in order.get("order_items", []):
        prod = ot.get("courses_description", {})
       
        item = OrderItem(
            item_id=ot["item_id"],
            course_id=ot["course_id"],
            name=prod.get("name", ""),
            description=prod.get("description", ""),
            price=ot["price"],
            type=prod.get("type", ""),
            duration=prod.get("duration", 0),
            sessions_per_week=prod.get("sessions_per_week", 0),
            minutes_per_session=prod.get("minutes_per_session", 0),
            instructor_name=prod.get("instructor_name", ""),
            subtotal=ot["subtotal"],
        )

        items_list[ot["item_id"]] = item
        
    return Order(
        order_id=order["order_id"],
        status=order["status"],
        payment=order["payment"],
        order_total=order["order_total"],
        discount_voucher=order["discount_voucher"],
        grand_total=order["grand_total"],
        created_at=order["created_at"],
        receiver_name=order.get("receiver_name", ""),
        receiver_phone_number=order.get("receiver_phone_number", ""),
        receiver_email=order.get("receiver_email", ""),
        admission_day=order.get("admission_day"),
        items=items_list,
    )
    
def _get_location_for_order(course_id: int) -> str:
    """
    Hàm nội bộ để lấy thông tin địa điểm/link học cho một khóa học.
    Truy vấn trực tiếp vào bảng locations bằng course_id.
    Trả về chuỗi thông tin hoặc chuỗi rỗng nếu không tìm thấy.
    """
    try:
        # Bước 1: Dùng course_id để truy vấn thẳng vào bảng locations
        location_response = (
            supabase_client.table("locations")
            .select("location_link")
            .eq("course_id", course_id)
            .execute()
        )
        
        day_response = (
            supabase_client.table("locations")
            .select("days_of_week")
            .eq("course_id", course_id)
            .execute()
        )
        
        locations = location_response.data
        days = day_response.data
        if not locations:
            return "" # Không có địa điểm, trả về chuỗi rỗng
        if not days:
            return "" # Không có ngày học, trả về chuỗi rỗng
        
        # Định dạng chuỗi kết quả để hiển thị
        location_links = [loc['location_link'] for loc in locations if loc.get('location_link')]
        day_of_weeks = [day['days_of_week'] for day in days if day.get('days_of_week')]
        if location_links and day_of_weeks:
            location_info = " | ".join(location_links)
            day_info = ", ".join(day_of_weeks)
            return f"Địa điểm/hình thức học: {location_info}\nNgày học: {day_info}\n"
            
        return ""
    except Exception as e:
        logger.error(f"Lỗi khi lấy location im lặng: {e}")
        return ""
    
@tool
def add_order_tool(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Sử dụng công cụ này để tạo một đơn hàng mới.

    Chức năng: Tạo một đơn hàng mới dựa trên các sản phẩm có trong giỏ hàng và thông tin khách hàng (tên, SĐT, email) đã được lưu trong state.
    """
    logger.info("add_order_tool được gọi")
    
    cart = state["cart"].copy()
    if not cart:
        logger.info("Giỏ hàng rỗng")
        return Command(
            update=build_update(
                content="Khách chưa muốn mua sản phẩm nào, hỏi khách",
                tool_call_id=tool_call_id
            )
        )
    
    logger.info("Giỏ hàng có sản phẩm")
    student_id = state.get("student_id")
    receiver_name = state.get("name")
    receiver_phone = state.get("phone_number")
    receiver_email = state.get("email")

    # Không có đủ thông tin khách
    if not all([student_id, receiver_name, receiver_phone, receiver_email]):
        logger.info(
            "Không có đủ thông tin khách "
            f"id: {student_id} | "
            f"name: {receiver_name} | "
            f"phone: {receiver_phone} | "
            f"email: {receiver_email}"
        )
        return Command(
            update=build_update(
                content=(
                    "Đây là các thông tin của khách:\n"
                    f"- Tên người nhận: {receiver_name if receiver_name else "Không có"}\n"
                    f"- Số điện thoại người nhận: {receiver_phone if receiver_phone else "Không có"}\n"
                    f"- Email người nhận: {receiver_email if receiver_email else "KHông có"}\n"
                    "Hỏi khách các thông tin còn thiếu"
                ),
                tool_call_id=tool_call_id
            )
        )

    try:
        logger.info("Đã đủ thông tin của khách -> lên đơn")
        # 1. Tính tổng giá trị giỏ hàng
        order_total = 0
        total_discount_amount = 0
        seen_products = state.get("seen_products", {})

        for item in cart.values():
            course_id = item["course_id"]
            product_details = seen_products.get(course_id)
            
            order_total += item["subtotal"]

            if product_details:
                promotion_rate = product_details.get("promotion", 0.0)
                original_price = product_details.get("price", 0)
                total_discount_amount += original_price * promotion_rate

        grand_total = order_total - total_discount_amount
        payment_methods = state.get("payment") if state.get("payment") else "chuyển khoản ngân hàng"
        first_item_course_id = next(iter(cart.values()))["course_id"]
        admission_day = _get_first_schedule_start_date(first_item_course_id)
        order_payload = {
            "student_id": student_id,
            "order_total": order_total,
            "discount_voucher": total_discount_amount,
            "grand_total": grand_total,
            "receiver_name": receiver_name, 
            "receiver_phone_number": receiver_phone, 
            "receiver_email": receiver_email, 
            "payment": payment_methods,
            "status": "pending",
            "admission_day": admission_day
        }
        
        order_res = (
            supabase_client.table('orders')
            .insert(order_payload)
            .execute()
        )
        
        if not order_res.data:
            logger.error("Lỗi ở cấp DB -> Không thể tạo đơn hàng")
            return Command(
                update=build_update(
                    content="Lỗi không thể tạo đơn hàng, xin khách thử lại"
                ),
                tool_call_id=tool_call_id
            )
        
        new_order_id = order_res.data[0].get("order_id")
        items_to_insert = []
        logger.info(f"Tạo bản ghi trong orders thành công với ID: {new_order_id}")
        
        for item in cart.values():
            # Lấy thông tin chi tiết của khóa học để biết tỷ lệ khuyến mãi
            product_details = seen_products.get(item["course_id"])
            promotion_rate = 0.0
            if product_details:
                promotion_rate = product_details.get("promotion", 0.0)

            # Tính toán subtotal chính xác sau khi đã áp dụng khuyến mãi
            discounted_subtotal = item["price"] * (1 - promotion_rate)
            items_to_insert.append({
                "order_id": new_order_id, 
                "course_id": item["course_id"],
                "price": item["price"],
                "subtotal": discounted_subtotal 
            })
         
        item_res = (
            supabase_client.table('order_items')
            .insert(items_to_insert)
            .execute()
        )
        
        if not item_res.data:
            logger.error("Lỗi ở cấp DB -> Không thể thêm sản phẩm vào trong order_items")
            return Command(
                update=build_update(
                    content=(
                        "Không thể thêm sản phẩm vào đơn hàng, "
                        "xin lỗi khách và hứa sẽ khắc phục sớm nhất"
                    ),
                    tool_call_id=tool_call_id
                )
            )
        
        logger.info("Thêm các sản phẩm trong giỏ hàng vào order items thành công")
        
        logger.info(f"Đang ghi log đơn hàng {new_order_id} vào Google Sheets (Order)...")
        try:
            order_sheet_logger = OrderSheetLogger()
            
            course_names_list = [
                state["seen_products"][item["course_id"]]["name"]
                for item in cart.values()
                if item["course_id"] in state["seen_products"]
            ]
            # Nối tên các khóa học lại, phân cách bởi dấu phẩy
            course_names_str = ", ".join(course_names_list)

            # 2. Gọi hàm log với tham số tên khóa học mới
            order_sheet_logger.log(
                order_id=new_order_id,
                receiver_name=order_payload["receiver_name"],
                receiver_phone_number=order_payload["receiver_phone_number"],
                receiver_email=order_payload["receiver_email"],
                course_names=course_names_str, 
                admission_day=order_payload["admission_day"],
                grand_total=order_payload["grand_total"],
                payment=order_payload["payment"],
            )
            logger.success(f"Ghi log đơn hàng {new_order_id} vào Google Sheets (Order) thành công!")
        except Exception as e:
            logger.error(f"Lỗi khi ghi log đơn hàng {new_order_id} vào Google Sheets (Order): {e}")
        
        order = _get_order_details(order_id=new_order_id)
        order_detail = _return_order_details(
            order_id=new_order_id, # Đã sửa: truyền vào new_order_id thay vì object order
            raw_order_detail=order
        )
        
        location_info = "\nThông tin địa điểm/link học:\n"
        has_location_info = False
        for item in cart.values():
            course_id = item["course_id"]
            course_name = state["seen_products"][course_id]["name"]
            location_details = _get_location_for_order(course_id) # Gọi hàm đã được refactor
            if location_details:
                location_info += f"Khóa học '{course_name}':\n{location_details}"
                has_location_info = True
        
        if not has_location_info:
            location_info = "\n(Thông tin địa điểm và link học sẽ được trung tâm gửi đến anh/chị sau ạ)"
        order_state = state["order"].copy() if state["order"] is not None else {}
        order_state[new_order_id] = _update_order_state(order=order)
        
        logger.info("Lên đơn thành công")
        return Command(
            update=build_update(
                content=(
                    "Tạo đơn hàng thành công, đây là đơn hàng của khách:\n"
                    f"{order_detail}\n"
                    f"{location_info}\n"
                    "Không được tóm gọn, phải liệt kê chi tiết, đầy đủ, không bịa đặt "
                    "không tạo phản hồi các thông tin dư thừa.\n"
                    "Thông báo thêm về việc trung tâm sẽ liên hệ để xác nhận và hướng dẫn thủ tục nhập học." # Thay đổi cho phù hợp ngữ cảnh khóa học
                ),
                tool_call_id=tool_call_id,
                order=order_state,
                cart={},
                seen_products={}
            )
        )

    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def cancel_order_tool(
    order_id: Annotated[Optional[int], "ID của đơn hàng cần hủy."],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """Sử dụng công cụ này để hủy một đơn hàng.

    Chức năng: Hủy một đơn hàng dựa trên ID của đơn hàng.

    Tham số:
        - order_id (int, tùy chọn): ID của đơn hàng cần hủy.
    """
    print("cancel_order_tool được gọi")
    
    order_state = state["order"].copy() if state["order"] is not None else {}
    
    if not order_state:
        logger.info("order trống -> không thể huỷ đơn")
        return Command(
            update=build_update(
                content="Không có thông tin đơn của khách, lấy các đơn của khách",
                tool_call_id=tool_call_id
            )
        )
    
    if not order_id:
        logger.info("Không thể xác định được order_id mà khách muốn huỷ")
        return Command(
            update=build_update(
                content="Không xác định được đơn hàng mà khách muốn chỉnh sửa, hỏi lại khách",
                tool_call_id=tool_call_id
            )
        )
    
    try:
        logger.info(f"Xác định được order_id mà khách muốn: {order_id}")
        
        response = (
            supabase_client.table('orders')
            .update({"status": "cancelled"})
            .eq('order_id', order_id)
            .neq('status', 'cancelled')
            .execute()
        )
        
        if not response.data:
            logger.error("Lỗi ở cấp DB -> Không thể huỷ đơn hàng")
            return Command(
                update=build_update(
                    content=f"Xảy ra lỗi trong lúc huỷ đơn hàng {order_id}, xin lỗi khách và hứa sẽ khắc phục sớm nhất",
                    tool_call_id=tool_call_id
                )
            )
        
        logger.info("Huỷ dơn hàng thành công")
        
        # Cập nhật vào state
        order_state[order_id]["status"] = "cancelled"
        
        return Command(
            update=build_update(
                content=f"Đã hủy thành công đơn hàng có ID {order_id}",
                tool_call_id=tool_call_id,
                order=order_state
            )
        )
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def get_customer_orders_tool(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Dùng công cụ này khi khách hàng muốn chỉnh sửa đơn hàng nhưng không cung cấp ID cụ thể, hoặc khi cần kiểm tra lịch sử đơn hàng của khách.

    Chức năng: Lấy danh sách các đơn hàng gần đây của khách hàng mà có thể chỉnh sửa được.
    """
    logger.info("get_customer_orders_tool được gọi")
    student_id = state.get("student_id")
    order_state = state["order"].copy() if state["order"] is not None else {}

    if not student_id:
        logger.info("Không tìm thấy student_id trong state")
        return Command(update=build_update(
            content="Lỗi không thấy student_id, xin lỗi khách và hứa sẽ khắc phục sớm nhất có thể",
            tool_call_id=tool_call_id
        ))

    logger.info(f"Tìm thấy student_id: {student_id}")
    try:
        all_editablt_orders = _get_all_editable_orders(
            student_id=student_id
        )

        if not all_editablt_orders:
            logger.info(f"Không tìm thấy đơn hàng nào cho student_id: {student_id}")
            return Command(
                update=build_update(
                    content="Thông báo khách chưa đặt đơn hàng nào",
                    tool_call_id=tool_call_id
                )
            )

        logger.info(f"Tìm thấy {len(all_editablt_orders)} đơn hàng cho student_id: {student_id}")

        order_detail = _return_all_editable_orders(
            student_id=student_id,
            list_raw_order_detail=all_editablt_orders
        )
        
        for order in all_editablt_orders:
            order_state[order["order_id"]] = _update_order_state(order=order)
        
        return Command(
            update=build_update(
                content=(
                    "Đây là đơn hàng mà khách có thể chỉnh sửa:\n"
                    f"{order_detail}\n\n"
                    "Bạn phải in ra dưới dạng rút gọn các đơn để khách xác định được "
                    "đơn khách muốn chỉnh sửa"
                ),
                tool_call_id=tool_call_id,
                order=order_state
            )
        )

    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def alter_item_order_tool(
    order_id: Annotated[Optional[int], "ID của đơn hàng cần chỉnh sửa."],
    old_course_id: Annotated[Optional[int], "ID của khóa học cũ cần thay thế trong đơn hàng."],
    new_course_id: Annotated[Optional[int], "ID của khóa học mới muốn thêm vào đơn hàng."],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    [Công cụ chính để đổi khóa học]
    Thay thế một khóa học cũ bằng một khóa học mới trong một đơn hàng đã tồn tại.
    Công cụ này sẽ tự động:
    1. Hủy khóa học cũ và thêm khóa học mới.
    2. Tính toán lại tổng tiền của đơn hàng.
    3. Kiểm tra chính sách hoàn tiền 30 ngày cho khóa học đã hủy.
    4. Gửi thông báo cho bộ phận CSKH nếu có trường hợp cần hoàn tiền.
    """
    logger.info("alter_item_order_tool được gọi")
    
    order_state = state.get("order", {})
    seen_products = state.get("seen_products", {})
    customer_name = state.get("name")
    customer_phone = state.get("phone_number")

    # --- 1. Kiểm tra các điều kiện đầu vào ---
    if not order_id or order_id not in order_state:
        return Command(update=build_update(content="Em chưa xác định được anh/chị muốn sửa đơn hàng nào. Anh/chị có thể cho em biết mã đơn hàng được không ạ?", tool_call_id=tool_call_id))
    
    if not old_course_id or not new_course_id:
        return Command(update=build_update(content="Để thay đổi khóa học, anh/chị vui lòng cho em biết khóa học cũ và khóa học mới mà anh/chị quan tâm nhé.", tool_call_id=tool_call_id))

    new_product_info = seen_products.get(new_course_id)
    if not new_product_info:
        return Command(update=build_update(content=f"Em chưa tìm thấy thông tin về khóa học mới (ID: {new_course_id}). Anh/chị có muốn em tìm thông tin về khóa học này không ạ?", tool_call_id=tool_call_id))

    try:
        # --- 2. Lấy thông tin đơn hàng và kiểm tra chính sách hoàn tiền ---
        order_details = _get_order_details(order_id)
        if not order_details:
             return Command(update=build_update(content=f"Không tìm thấy đơn hàng với ID {order_id}.", tool_call_id=tool_call_id))

        created_at_date = datetime.fromisoformat(order_details["created_at"])
        days_since_creation = (datetime.now(created_at_date.tzinfo) - created_at_date).days
        refund_possible = days_since_creation < 30

        # --- 3. Thực hiện các thao tác trên Database ---
        order_to_modify = order_state.get(order_id, {})
        item_id_to_delete = None
        item_price_to_refund = 0

        for item in order_to_modify.get("items", {}).values():
            if item["course_id"] == old_course_id:
                item_id_to_delete = item["item_id"]
                item_price_to_refund = item["price"]
                break

        if not item_id_to_delete:
            return Command(update=build_update(content=f"Em không tìm thấy khóa học (ID: {old_course_id}) trong đơn hàng {order_id} của anh/chị.", tool_call_id=tool_call_id))

        # Xóa item cũ
        supabase_client.table('order_items').delete().eq('item_id', item_id_to_delete).execute()
        logger.info(f"Đã xóa item {item_id_to_delete} (course_id: {old_course_id}) khỏi đơn hàng {order_id}")

        # --- BẮT ĐẦU THAY ĐỔI ---
        # Thêm item mới với subtotal đã được tính khuyến mãi
        new_price = new_product_info["price"]
        new_promotion = new_product_info.get("promotion", 0.0)
        new_subtotal = new_price * (1 - new_promotion)
        
        new_item_payload = {
            "order_id": order_id, 
            "course_id": new_course_id, 
            "price": new_price, 
            "subtotal": new_subtotal
        }
        supabase_client.table('order_items').insert(new_item_payload).execute()
        logger.info(f"Đã thêm khóa học mới (course_id: {new_course_id}) vào đơn hàng {order_id}")

        # Lấy lại tất cả các item trong đơn hàng để tính toán lại tổng giá trị
        updated_order_items = _get_order_details(order_id).get("order_items", [])
        
        new_order_total = 0
        total_discount_amount = 0

        for item in updated_order_items:
            prod_info = item.get("courses_description", {})
            price = item.get("price", 0)
            promotion_rate = prod_info.get("promotion", 0.0)
            
            new_order_total += price
            total_discount_amount += price * promotion_rate

        new_grand_total = new_order_total - total_discount_amount
        
        # Cập nhật lại đơn hàng chính với các giá trị chính xác
        update_payload = {
            "order_total": new_order_total, 
            "discount_voucher": total_discount_amount, 
            "grand_total": new_grand_total
        }
        # --- KẾT THÚC THAY ĐỔI ---
        supabase_client.table('orders').update(update_payload).eq('order_id', order_id).execute()
        logger.info(f"Đã cập nhật tổng giá trị cho đơn hàng {order_id}")
        
        # --- 4. Xử lý thông báo và phản hồi ---
        final_order_data = _get_order_details(order_id)
        formatted_details = _return_order_details(order_id=order_id, raw_order_detail=final_order_data)
        response_content = f"Em đã cập nhật thành công đơn hàng của anh/chị. Dưới đây là thông tin chi tiết:\n{formatted_details}"

        if refund_possible:
            logger.info(f"Đơn hàng {order_id} đủ điều kiện hoàn tiền. Gửi thông báo cho admin.")
            notification_summary = (
                f"Khách hàng '{customer_name}' (SĐT: {customer_phone}) đã đổi khóa học trong đơn hàng #{order_id}. "
                f"Khóa học cũ (ID: {old_course_id}) được đăng ký {days_since_creation} ngày trước, đủ điều kiện hoàn tiền. "
                f"Vui lòng hỗ trợ hoàn tiền cho học viên."
            )
            send_altercourse_notification_tool.invoke({
                "customer_name": customer_name, "customer_phone": customer_phone,
                "issue_summary": notification_summary, "chat_history_url": "about:blank"
            })
            response_content += (
                f"\n\n**Thông báo thêm:**\n"
                f"Do yêu cầu đổi được thực hiện trong vòng 30 ngày, "
                f"bộ phận CSKH sẽ liên hệ để xác nhận và tiến hành hoàn lại học phí cho khóa học đã hủy."
            )

        # --- 5. Cập nhật state ---
        if final_order_data:
            order_state[order_id] = _update_order_state(order=final_order_data)

        return Command(
            update=build_update(
                content=response_content,
                tool_call_id=tool_call_id,
                order=order_state
            )
        )

    except Exception as e:
        logger.error(f"Lỗi trong alter_item_order_tool: {e}")
        return Command(update=build_update(content="Đã có lỗi xảy ra trong quá trình cập nhật, anh/chị vui lòng thử lại sau.", tool_call_id=tool_call_id))

@tool
def modify_receiver_info_tool(
    order_id: Annotated[Optional[int], "ID của đơn hàng cần cập nhật thông tin người nhận."],
    new_name: Annotated[Optional[str], "Tên người nhận mới."],
    new_phone: Annotated[Optional[str], "Số điện thoại người nhận mới."],
    new_email: Annotated[Optional[str], "Email người nhận mới."],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này để cập nhật thông tin người nhận (tên, SĐT, email) cho một đơn hàng cụ thể đã tồn tại.

    Chức năng: Chỉnh sửa thông tin người nhận trên một đơn hàng.

    Tham số:
        - order_id (int): ID của đơn hàng cần cập nhật.
        - new_name (str, tùy chọn): Tên mới của người nhận.
        - new_phone (str, tùy chọn): Số điện thoại mới của người nhận.
        - new_email (str, tùy chọn): Email mới của người nhận.
    """
    logger.info("modify_receiver_info_tool được gọi")
    
    order_state = state.get("order", {})

    if not order_id or order_id not in order_state:
        return Command(
            update=build_update(
                content="Em chưa xác định được anh/chị muốn chỉnh sửa thông tin cho đơn hàng nào. Anh/chị vui lòng cung cấp mã đơn hàng nhé.",
                tool_call_id=tool_call_id
            )
        )

    if not any([new_name, new_email, new_phone]):
        return Command(
            update=build_update(
                content="Để cập nhật, anh/chị vui lòng cung cấp ít nhất một thông tin mới (tên, số điện thoại, hoặc email) ạ.",
                tool_call_id=tool_call_id
            )
        )

    try:
        update_payload = {}
        if new_name:
            update_payload['receiver_name'] = new_name
        if new_phone:
            update_payload['receiver_phone_number'] = new_phone
        if new_email:
            update_payload['receiver_email'] = new_email

        logger.info(f"Cập nhật thông tin người nhận cho đơn hàng {order_id}: {update_payload}")
        
        response = (
            supabase_client.table('orders')
            .update(update_payload)
            .eq('order_id', order_id)
            .execute()
        )
        
        if not response.data:
            logger.error(f"Lỗi DB: Không thể cập nhật thông tin người nhận cho đơn hàng {order_id}")
            return Command(
                update=build_update(
                    content=f"Đã có lỗi xảy ra trong quá trình cập nhật đơn hàng {order_id}. Anh/chị vui lòng thử lại sau.",
                    tool_call_id=tool_call_id
                )
            )

        # Lấy lại thông tin đơn hàng đầy đủ và cập nhật state
        final_order_data = _get_order_details(order_id)
        if final_order_data:
            order_state[order_id] = _update_order_state(order=final_order_data)
        
        formatted_details = _return_order_details(order_id=order_id, raw_order_detail=final_order_data)

        logger.info(f"Cập nhật thông tin người nhận cho đơn hàng {order_id} thành công")
        return Command(
            update=build_update(
                content=(
                    "Em đã cập nhật thành công thông tin người nhận cho đơn hàng của mình. Dưới đây là thông tin chi tiết:\n"
                    f"{formatted_details}"
                ),
                tool_call_id=tool_call_id,
                order=order_state,
            )
        )

    except Exception as e:
        logger.error(f"Lỗi trong modify_receiver_info_tool: {e}")
        raise

@tool
def alter_admission_day_tool(
    order_id: Annotated[int, "ID của đơn hàng cần thay đổi."],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Sử dụng công cụ này để tự động dời lịch học của một đơn hàng sang khóa kế tiếp.
    Công cụ sẽ tự tính ngày khai giảng mới dựa trên ngày hiện tại và thời lượng khóa học.
    """
    logger.info(f"alter_admission_day_tool được gọi cho đơn {order_id}")

    try:
        # Bước 1: Lấy thông tin đơn hàng hiện tại
        order_details = _get_order_details(order_id)

        if not order_details:
            raise Exception("Không tìm thấy đơn hàng.")

        current_admission_day_str = order_details.get("admission_day")
        if not current_admission_day_str:
            raise Exception("Đơn hàng chưa có ngày khai giảng để dời.")
            
        # Lấy duration từ khóa học ĐẦU TIÊN trong đơn
        first_item = order_details.get("order_items", [{}])[0]
        duration_in_weeks = first_item.get("courses_description", {}).get("duration")
        if duration_in_weeks is None:
            raise Exception("Không tìm thấy thông tin thời lượng khóa học.")

        # Bước 2: Tính toán ngày khai giảng mới
        current_admission_date = datetime.strptime(current_admission_day_str, "%Y-%m-%d")
        new_admission_date = current_admission_date + timedelta(weeks=duration_in_weeks)
        new_admission_day_str = new_admission_date.strftime("%Y-%m-%d")

        # Bước 3: Cập nhật ngày mới vào bảng orders
        update_response = (
            supabase_client.table("orders")
            .update({"admission_day": new_admission_day_str})
            .eq("order_id", order_id)
            .execute()
        )

        if not update_response.data:
            raise Exception("Cập nhật ngày khai giảng trong DB thất bại.")

        # Bước 4: Cập nhật state và tạo phản hồi cho khách
        updated_order = update_response.data[0]
        order_state = state.get("order", {}).copy()
        order_state[order_id] = _update_order_state(order=updated_order)
        
        # Tạo phản hồi theo mẫu
        formatted_new_date = new_admission_date.strftime("%d/%m/%Y")
        response_content = (
            f"Dạ được ạ. Em hiểu rồi ạ. Em đã cập nhật dời lịch học của mình sang khóa khai giảng ngày {formatted_new_date} tiếp theo. "
            f"Mã đơn hàng #{order_id} của mình vẫn được giữ nguyên. "
            "Em đã gửi lại xác nhận vào SĐT của mình ạ."
        )

        logger.info(f"Đã dời lịch học cho đơn hàng {order_id} sang ngày {new_admission_day_str}")
        return Command(
            update=build_update(
                content=response_content,
                tool_call_id=tool_call_id,
                order=order_state
            )
        )

    except Exception as e:
        logger.error(f"Lỗi trong alter_admission_day_tool: {e}")
        return Command(
            update=build_update(
                content="Đã có lỗi xảy ra trong quá trình xử lý, anh/chị vui lòng thử lại sau.",
                tool_call_id=tool_call_id
            )
        )