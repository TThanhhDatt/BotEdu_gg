from core.tools.product_search_tool import get_courses_tool, get_qna_tool, get_schedule_tool, get_promotions_tool
from core.tools.cart_tool import add_item_cart_tool, cancel_item_cart_tool
from core.tools.customer_tool import modify_customer_tool
from core.tools.order_tool import (
    add_order_tool, 
    cancel_order_tool,
    alter_item_order_tool,
    get_customer_orders_tool,
    modify_receiver_info_tool,
    alter_admission_day_tool
)

course_toolbox = [
    get_courses_tool,
    get_qna_tool,
    get_schedule_tool,
    get_promotions_tool
]

enrollment_toolbox = [
    get_courses_tool,
    add_order_tool,
    add_item_cart_tool,
    cancel_item_cart_tool,
    modify_customer_tool
]

modify_toolbox = [
    get_courses_tool,
    get_customer_orders_tool,
    cancel_order_tool,
    modify_receiver_info_tool,
    get_schedule_tool, 
    alter_admission_day_tool,
    alter_item_order_tool
]