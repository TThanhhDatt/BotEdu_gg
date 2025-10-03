from langgraph.types import Command
from typing import Annotated, Optional
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolCallId

from core.utils.tool_function import build_update
from core.graph.state import AgentState, Cart, SeenProducts

from log.logger_config import setup_logging

logger = setup_logging(__name__)

def _return_cart(
    seen_products: dict[int, SeenProducts], 
    cart: dict[int, Cart],
    name: Optional[str] = None,
    phone_number: Optional[str] = None,
    email: Optional[str] = None
) -> str:
    """
    Kết xuất thông tin giỏ hàng và tổng hợp thành chuỗi mô tả chi tiết.

    Args:
        seen_products (dict[int, SeenProducts]): Tập các khóa học đã xem dùng để tra cứu thông tin hiển thị.
        cart (dict[int, Cart]): Giỏ hàng hiện tại (course_id -> dòng hàng).
        name (Optional[str]): Tên khách hàng nếu đã có.
        phone_number (Optional[str]): Số điện thoại khách hàng nếu đã có.
        email (Optional[str]): Email khách hàng nếu đã có.

    Returns:
        str: Chuỗi mô tả giỏ hàng, tổng tiền và thông tin khách hàng.
    """
    order_total = 0
    total_discount_amount = 0
    cart_detail = ""
    index = 1
    
    for item in cart.values():
        product = seen_products[item['course_id']]
        
        # Sửa lỗi: Cộng dồn subtotal vào order_total
        order_total += item['subtotal']

        course_id = product["course_id"]
        course_name = product["name"]
        
        description = product["description"]
        type = product["type"]
        duration = product["duration"]
        price = product["price"]
        sessions_per_week = product["sessions_per_week"]
        minutes_per_session = product["minutes_per_session"]
        instructor_name = product["instructor_name"]
        
        promotion_rate = product.get("promotion", 0.0) # Mặc định là 0 nếu không có
        original_price = product.get("price", 0)
        total_discount_amount += original_price * promotion_rate
        
        cart_detail += (
            f"STT: {index}\n"
            f"Mã khóa học: {course_id}.\n"
            f"Tên khóa học: {course_name}.\n"
            f"Mô tả: {description}.\n"
            f"Hình thức: {type}.\n"
            f"Thời lượng: {duration} tuần.\n"
            f"Số buổi học mỗi tuần: {sessions_per_week} buổi.\n"
            f"Số phút mỗi buổi học: {minutes_per_session} phút.\n"
            f"Tên giảng viên: {instructor_name}.\n"
            f"Học phí: {price:,.0f} VNĐ.\n\n" 
        )
        
        index += 1
    
    # Cập nhật logic tính toán và hiển thị voucher
    discount_amount = total_discount_amount
    grand_total = order_total - discount_amount

    cart_detail += (
        f"Tên học viên: {name if name else "Chưa có"}.\n"
        f"Số điện thoại học viên: {phone_number if phone_number else "Chưa có"}.\n"
        f"Email học viên: {email if email else "Chưa có"}.\n"
    )
    
    return cart_detail

@tool
def add_item_cart_tool(
    course_id: Annotated[Optional[int], (
        "Là ID của khóa học khách muốn thêm, lấy từ seen_products"
    )],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
    
) -> Command:
    """
    Sử dụng công cụ này để thêm khóa học vào giỏ hàng.

    Chức năng: Dùng để thêm một khóa học vào giỏ hàng.

    Tham số:
        - course_id (int, tùy chọn): Là ID của khóa học mà khách hàng muốn thêm vào giỏ hàng. ID này được lấy từ danh sách các khóa học mà khách hàng đã xem (seen_products).
    """
    logger.info("add_item_cart_tool được gọi")
    # Đảm bảo khách đã xem trước ít nhắt 1 sản phẩm
    if not state["seen_products"]:
        logger.info("seen_products rỗng -> khách chưa xem sản phẩm nào")
        return Command(
            update=build_update(
                content="Khách chưa xem sản phẩm nào, hỏi khách có muốn mua sản phẩm nào không",
                tool_call_id=tool_call_id
            )
        )
        
    if not course_id:
        logger.info("Không xác định được course_id")
        return Command(
            update=build_update(
                content="Không thể xác định được sản phẩm khách muốn mua, hỏi lại khách",
                tool_call_id=tool_call_id
            )
        )
    
    try:
        logger.info("seen_products có sản phẩm và xác định được course_id")
        cart = state["cart"].copy() if state["cart"] is not None else {}
        price = state["seen_products"][course_id]["price"]
        
        cart[course_id] = Cart(
            course_id=course_id,
            price=price,
            subtotal= price
        )
        
        cart_detail = _return_cart(
            seen_products=state["seen_products"],
            cart=cart,
            name=state["name"],
            phone_number=state["phone_number"],
            email=state["email"]
        )
        
        logger.info(f"Thêm sản phẩm {course_id} vào giỏ hàng thành công")
        
        return Command(
            update=build_update(
                content=(
                    "Thêm sản phẩm <bạn hãy tự điền tên> vào giỏ hàng thành công, đây là giỏ hàng:\n"
                    f"{cart_detail}\n"
                    "Bạn phải liệt kê đầy đủ, không được rút gọn hay bịa đặt thông tin mới\n"
                    "Nếu trong 3 thông tin name, phone_number, hoặc email thiếu thông tin nào "
                    "thì hỏi khách thông tin đó\n"
                    "Nếu khách có yêu cầu khác thì gọi tool thực hiện yêu cầu đó\n"
                    "Nếu khách không có yêu cầu khác thì BẮT BUỘC KHÔNG được gọi "
                    "tool nào nữa và phải dừng lại và tạo phản hồi để khách xác nhận.\n"
                ),
                tool_call_id=tool_call_id,
                cart=cart
            )
        )
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def cancel_item_cart_tool(
    course_id: Annotated[Optional[int], (
        "Là khoá của dict seen_products, đại diện "
        "cho sản phẩm khách muốn xoá"
    )],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
    
) -> Command:
    """
    Sử dụng công cụ này để xoá một khóa học khỏi giỏ hàng.

    Chức năng: Xoá một khóa học khỏi giỏ hàng.

    Tham số:
        - course_id (int, tùy chọn): ID của khóa học mà khách hàng muốn xoá khỏi giỏ hàng.
    """
    logger.info("cancel_item_cart_tool được gọi")
    
    cart = state["cart"].copy() if state["cart"] is not None else {}
    if not cart:
        logger.info("Giỏ hàng rỗng")
        return Command(
            update=build_update(
                content="Khách chưa muốn mua sản phẩm nào, hỏi khách có muốn xem sản phẩm nào không",
                tool_call_id=tool_call_id
            )
        )
        
    if not course_id:
        logger.info("Không xác định được course_id")
        return Command(
            update=build_update(
                content="Không xác định được sản phẩm khách muốn xoá khỏi giỏ hàng, nói khách miêu tả rõ hơn",
                tool_call_id=tool_call_id
            )
        )
    
    if course_id not in cart:
        logger.info("Sản phẩm muốn xoá không có trong giỏ hàng")
        return Command(
            update=build_update(
                content="Sản phẩm khách muốn xoá không có trong giỏ hàng, hỏi khách kiểm tra lại",
                tool_call_id=tool_call_id
            )
        )
    
    try:
        logger.info("Đã có đầy đủ thông tin để xoá sản phẩm khỏi giỏ hàng")
        del cart[course_id]
        
        if not cart:
            logger.info("Giỏ hàng trống sau khi xoá sản phẩm")
            return Command(
                update=build_update(
                    content="Xoá sản phẩm khỏi giỏ hàng thành công. Giỏ hàng hiện tại trống. Hỏi khách có muốn xem sản phẩm nào không",
                    tool_call_id=tool_call_id,
                    cart=cart
                )
            )
        
        cart_detail = _return_cart(
            seen_products=state["seen_products"],
            cart=cart,
            name=state["name"],
            phone_number=state["phone_number"],
            email=state["email"]
        )
        logger.info("Xoá sản phẩm khỏi giỏ hàng thành công")
        return Command(
            update=build_update(
                content=(
                    "Xoá sản phẩm <bạn hãy tự điền tên> khỏi giỏ hàng thành công, đây là giỏ hàng:\n"
                    f"{cart_detail}\n"
                    "Bạn phải liệt kê đầy đủ, không được rút gọn hay bịa đặt thông tin mới\n"
                    "Nếu trong 3 thông tin name, phone_number, hoặc email thiếu thông tin nào "
                    "thì hỏi khách thông tin đó\n"
                    "Nếu khách có yêu cầu khác thì gọi tool thực hiện yêu cầu đó\n"
                    "Nếu khách không có yêu cầu khác thì BẮT BUỘC KHÔNG được gọi "
                    "tool nào nữa và phải dừng lại và tạo phản hồi để khách xác nhận.\n"
                ),
                tool_call_id=tool_call_id,
                cart=cart
            )
        )
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise
    
@tool
def alter_item_cart_tool(
    course_id: Annotated[Optional[int], (
        "Là khoá của dict seen_products, đại diện "
        "cho sản phẩm khách muốn thay đổi"
    )],
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
    
) -> Command:
    """
    Sử dụng công cụ này để thay đổi một khóa học trong giỏ hàng.

    Chức năng: Thay đổi một khóa học trong giỏ hàng.

    Tham số:
        - course_id (int, tùy chọn): ID của khóa học mà khách hàng muốn thay đổi trong giỏ hàng.
    """
    logger.info("alter_item_cart_tool được gọi")
    
    cart = state["cart"].copy() if state["cart"] is not None else {}
    if not cart:
        logger.info("Giỏ hàng rỗng")
        return Command(
            update=build_update(
                content="Khách chưa muốn mua sản phẩm nào, hỏi khách có muốn xem sản phẩm nào không",
                tool_call_id=tool_call_id
            )
        )
        
    if not course_id:
        logger.info("Không xác định được course_id")
        return Command(
            update=build_update(
                content="Không xác định được sản phẩm khách muốn thay đổi trong giỏ hàng, nói khách miêu tả rõ hơn",
                tool_call_id=tool_call_id
            )
        )
    
    if course_id not in cart:
        logger.info("Sản phẩm muốn thay đổi không có trong giỏ hàng")
        return Command(
            update=build_update(
                content="Sản phẩm khách muốn thay đổi không có trong giỏ hàng, hỏi khách kiểm tra lại",
                tool_call_id=tool_call_id
            )
        )
    
    try:
        logger.info("Đã có đầy đủ thông tin để thay đổi sản phẩm trong giỏ hàng")
        price = state["seen_products"][course_id]["price"]
        
        cart[course_id] = Cart(
            course_id=course_id,
            price=price,
            subtotal= price
        )
        
        cart_detail = _return_cart(
            seen_products=state["seen_products"],
            cart=cart,
            name=state["name"],
            phone_number=state["phone_number"],
            email=state["email"]
        )
        
        logger.info("Thay đổi sản phẩm trong giỏ hàng thành công")
        return Command(
            update=build_update(
                content=(
                    "Thay đổi sản phẩm <bạn hãy tự điền tên> trong giỏ hàng thành công, đây là giỏ hàng:\n"
                    f"{cart_detail}\n"
                    "Bạn phải liệt kê đầy đủ, không được rút gọn hay bịa đặt thông tin mới\n"
                    "Nếu trong 3 thông tin name, phone_number, hoặc email thiếu thông tin nào "
                    "thì hỏi khách thông tin đó\n"
                    "Nếu khách có yêu cầu khác thì gọi tool thực hiện yêu cầu đó\n"
                    "Nếu khách không có yêu cầu khác thì BẮT BUỘC KHÔNG được gọi "
                    "tool nào nữa và phải dừng lại và tạo phản hồi để khách xác nhận.\n"
                ),
                tool_call_id=tool_call_id,
                cart=cart
            )
        )
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise

@tool
def alter_cart_tool(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId]
    
) -> Command:
    """
    Sử dụng công cụ này để thay đổi giỏ hàng.

    Chức năng: Thay đổi giỏ hàng.

    Tham số:
        - Không có tham số.
    """
    logger.info("alter_cart_tool được gọi")
    
    cart = state["cart"].copy() if state["cart"] is not None else {}
    if not cart:
        logger.info("Giỏ hàng rỗng")
        return Command(
            update=build_update(
                content="Khách chưa muốn mua sản phẩm nào, hỏi khách có muốn xem sản phẩm nào không",
                tool_call_id=tool_call_id
            )
        )
    
    try:
        logger.info("Đã có giỏ hàng để thay đổi")
        cart_detail = _return_cart(
            seen_products=state["seen_products"],
            cart=cart,
            name=state["name"],
            phone_number=state["phone_number"],
            email=state["email"]
        )
        
        logger.info("Trình bày giỏ hàng để khách thay đổi")
        return Command(
            update=build_update(
                content=(
                    "Đây là giỏ hàng hiện tại của bạn:\n"
                    f"{cart_detail}\n"
                    "Bạn phải liệt kê đầy đủ, không được rút gọn hay bịa đặt thông tin mới\n"
                    "Hãy hỏi khách muốn thay đổi gì trong giỏ hàng này\n"
                    "Nếu trong 3 thông tin name, phone_number, hoặc email thiếu thông tin nào "
                    "thì hỏi khách thông tin đó\n"
                    "Nếu khách có yêu cầu khác thì gọi tool thực hiện yêu cầu đó\n"
                    "Nếu khách không có yêu cầu khác thì BẮT BUỘC KHÔNG được gọi "
                    "tool nào nữa và phải dừng lại và tạo phản hồi để khách xác nhận.\n"
                ),
                tool_call_id=tool_call_id,
                cart=cart
            )
        )
    except Exception as e:
        logger.error(f"Lỗi: {e}")
        raise      