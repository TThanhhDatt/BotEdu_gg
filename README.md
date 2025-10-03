# AI Agent cho Đào tạo (Training Agent)

Phiên bản README này mô tả một hệ thống AI Agents chuyên cho kịch bản đào tạo (corporate/training/learning), được phát triển trên nền tảng multi-agent để tự động hoá quy trình tư vấn đào tạo, lên lịch, quản lý học viên và báo cáo.

Mục tiêu chính
- Tự động hoá tương tác với người dùng để thu thập nhu cầu đào tạo.
- Xây dựng lộ trình khóa học, đề xuất chương trình phù hợp.
- Lên lịch, lưu thông tin học viên và kết nối với bộ phận phụ trách (CS/Training).
- Hỗ trợ các thao tác hậu cần: đăng ký, báo giá, chuyển giao tài liệu và theo dõi tiến trình học.

Những điểm nổi bật
- Kiến trúc Multi-agent (Supervisor + Specialist agents).
- Stateful conversation: lưu trữ trạng thái người dùng (AgentState).
- Tích hợp database (Supabase) để lưu đơn đăng ký, lịch và lịch sử.
- Ghi log / thông báo (Google Sheets / internal notification tool) cho CSKH và đội đào tạo.

## Kiến trúc tổng quan
- Supervisor Agent: phủ nhận / chuyển hướng intent, chọn agent chuyên trách (course advisor, enrollment, escalation...).
- Course Advisor Agent: phân tích nhu cầu đào tạo, gợi ý chương trình, cấu trúc nội dung và chi phí.
- Enrollment Agent: quản lý đăng ký, giỏ hàng khóa học, tạo đơn đăng ký và xử lý thanh toán sơ bộ.
- Escalation / Supervisor: chuyển yêu cầu phức tạp sang nhân viên thật, log và gửi thông báo.
- Tools: tập hợp helper functions để thao tác DB (Supabase), ghi log lên Google Sheets, gửi notification nội bộ.

## Công nghệ sử dụng
- Python 3.10+
- FastAPI (API endpoint)
- LangChain, LangGraph (agent orchestration)
- OpenAI (hoặc model tuỳ chọn) cho NLU/NLG
- Supabase (Postgres) làm database
- python-dotenv để quản lý biến môi trường

## Cài đặt nhanh (local)
1. Clone repository và chuyển vào thư mục dự án

```powershell
git clone <your-repository-url>
cd ChatbotCSKH
```

2. Tạo và kích hoạt virtualenv (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Cài dependencies

```powershell
pip install -r requirements.txt
```

4. Tạo file `.env` ở thư mục gốc và thêm các biến cần thiết (ví dụ):

```text
SUPABASE_URL="YOUR_SUPABASE_URL"
SUPABASE_KEY="YOUR_SUPABASE_SERVICE_ROLE_OR_ANON_KEY"
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

# Optional / tracing
LANGSMITH_TRACING="true"
LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
LANGSMITH_API_KEY="YOUR_LANGSMITH_API_KEY"

# Google Sheets logger (nếu sử dụng)
GOOGLE_SHEETS_CREDENTIALS_PATH="connection/google_auth.json"

# Model selection
MODEL_EMBEDDING="text-embedding-3-small"
MODEL_ORCHESTRATOR="gpt-4.1-mini"
MODEL_SPECIALIST="gpt-4.1-mini"
```

5. Chạy server (local)

```powershell
uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```

## Cách dùng cơ bản
- Gửi yêu cầu tới API chat (ví dụ `/api/v1/chat`) hoặc khởi chạy `test.py` để tương tác trên terminal.
- Các agent xử lý input, cập nhật `AgentState`, và gọi tool để thao tác DB / gửi notification / ghi log.

## Cấu trúc thư mục chính (tóm tắt)
- `core/graph/` - định nghĩa các agent, state, prompt
- `core/tools/` - bộ công cụ (order, cart, notification, product search, ...) được agent gọi
- `connection/` - kết nối đến Supabase, Google Sheets credential
- `services/` - luồng xử lý chat, adapter API
- `database/` - logic kết nối DB (supabase client)

## Lưu ý vận hành cho môi trường đào tạo
- Xác định chuẩn dữ liệu `promotion`/discount: lưu dưới dạng tỷ lệ (0.1 cho 10%) hoặc số tiền; cần nhất quán.
- Log mọi escalation lên Google Sheets / Slack để đội Training có thể follow-up.
- Tránh lưu secret trong repo; dùng Secrets Manager hoặc biến môi trường.

## Tài liệu cho dev
- Thêm agent mới: tạo module agent trong `core/graph/`, thêm prompts ở `core/prompts/` và công cụ cần thiết trong `core/tools/`.
- Kiểm thử: viết unit tests cho `core/tools/*` trước khi tích hợp với agent.

## Next steps (gợi ý nâng cấp)
- Thêm pipeline fine-tune/LLM specialization cho đề xuất chương trình đào tạo.
- Thêm dashboard admin để xem leads, đơn đăng ký và trạng thái học viên.
- Hệ thống hoá policy discount / voucher cho training packages.

---

Nếu bạn muốn, tôi có thể:
- Chuẩn hoá các biến môi trường và tạo `.env.example`.
- Viết bộ unit test nhỏ cho logic tính tổng đơn và khuyến mãi.
- Tạo script mẫu để demo luồng: tư vấn -> tạo đơn -> ghi log -> escalate.

Chọn một trong các mục trên để tôi tiếp tục hỗ trợ.

