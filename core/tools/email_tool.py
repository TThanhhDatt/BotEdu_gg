# ChatbotCSKH/core/tools/email_tool.py

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from langchain_core.tools import tool
from log.logger_config import setup_logging

logger = setup_logging(__name__)

@tool
def send_escalation_email_tool(
    recipient_email: str,
    customer_name: str,
    customer_phone: str,
    issue_summary: str
) -> str:
    """
    Gửi email thông báo về một yêu cầu cần xử lý khẩn cấp đến email của nhân viên.
    """
    # Lấy thông tin cấu hình SMTP từ biến môi trường
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass, recipient_email]):
        error_msg = "Cấu hình SMTP hoặc email người nhận chưa đầy đủ trong file .env."
        logger.error(error_msg)
        return error_msg

    try:
        # --- Tạo nội dung email với định dạng HTML ---
        subject = f"🚨 Yêu Cầu Hỗ Trợ Khẩn Cấp Mới Từ Chatbot - KH: {customer_name or 'Chưa rõ'}"

        # Use a plain template string (not an f-string) because CSS/HTML contains many braces
        html_template = """
            <!DOCTYPE html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <title>Yêu cầu hỗ trợ khẩn cấp</title>
  </head>
  <body style="margin:0; padding:0; background:#0f172a; font-family:Arial,Helvetica,sans-serif; color:#e6eef8;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#0f172a; padding:20px;">
      <tr>
        <td align="center">
          <!-- Card -->
          <table width="600" cellpadding="0" cellspacing="0" border="0" 
                 style="background:#111827; border-radius:12px; overflow:hidden; box-shadow:0 6px 18px rgba(0,0,0,0.5);">
            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(90deg,#ff6b6b,#7c5cff); padding:16px; text-align:center; color:#fff; font-size:20px; font-weight:bold;">
                🚨 Yêu cầu hỗ trợ khẩn cấp mới
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:20px;">
                <p style="margin:0 0 12px 0; font-size:15px; color:#9aa8c2;">
                  Ghi nhận và chuyển tới đội Đào tạo / CSKH — vui lòng phản hồi ngay.
                </p>

                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;">
                  <tr>
                    <td width="60" valign="top" align="center">
                      <div style="width:50px; height:50px; border-radius:8px; background:linear-gradient(135deg,#ff6b6b,#7c5cff); color:#0f172a; font-weight:bold; display:flex; align-items:center; justify-content:center; font-size:16px;">
                        
                      </div>
                    </td>
                    <td valign="top" style="padding-left:12px; font-size:14px;">
                      <div><b>Khách hàng:</b> {customer_name}</div>
                      <div style="color:#9aa8c2; font-size:13px;"><b>SĐT:</b> {customer_phone}</div>
                      <div style="color:#9aa8c2; font-size:13px;"><b>Thời gian:</b> {timestamp}</div>
                    </td>
                  </tr>
                </table>

                <div style="background:#1e293b; border:1px solid #334155; border-radius:8px; padding:12px; font-size:14px; color:#cbd5e1; line-height:1.5; margin-bottom:16px;">
                  <strong>Tóm tắt vấn đề:</strong>
                  <div style="margin-top:6px;">{issue_summary}</div>
                </div>

                <!-- Action Buttons -->
                <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
                  <tr>
                    <td>
                      <a href="{GOOGLE_SHEET_URL}" target="_blank"
                         style="background:linear-gradient(90deg,#ff6b6b,#7c5cff); color:#0f172a; text-decoration:none; padding:10px 16px; border-radius:6px; font-weight:bold; font-size:14px; display:inline-block; margin-right:8px;">
                        📑 Mở Google Sheet
                      </a>
                    </td>
                    <td>
                      <a href="tel:{customer_phone}"
                         style="background:#1e293b; color:#e6eef8; text-decoration:none; padding:10px 16px; border-radius:6px; font-weight:bold; font-size:14px; display:inline-block; margin-right:8px;">
                        📞 Gọi ngay
                      </a>
                    </td>
                    <td>
                      <a href="sms:{customer_phone}"
                         style="background:#1e293b; color:#e6eef8; text-decoration:none; padding:10px 16px; border-radius:6px; font-weight:bold; font-size:14px; display:inline-block;">
                        💬 Nhắn SMS
                      </a>
                    </td>
                  </tr>
                </table>

                <!-- Footer -->
                <div style="font-size:12px; color:#94a3b8; text-align:center; border-top:1px solid #334155; padding-top:12px;">
                  Email này được gửi tự động từ hệ thống Chatbot CSKH. Vui lòng không trả lời trực tiếp.
                </div>
              </td>
            </tr>
          </table>
          <!-- End Card -->
        </td>
      </tr>
    </table>
  </body>
</html>
        """

        # Prepare safe replacement values
        cname = customer_name or 'Chưa cung cấp'
        cphone = customer_phone or 'Chưa cung cấp'
        ts = datetime.now().strftime('%H:%M:%S - %d/%m/%Y')
        internal_note_val = ''
        issue_val = issue_summary or ''
        initials = 'KH'
        if customer_name:
            parts = [p for p in customer_name.split() if p]
            if parts:
                initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else ''))[:2].upper()

        # Replace placeholders used in the template. We replace exact literal tokens present
        html_body = html_template
        html_body = html_body.replace("{customer_name or 'Chưa cung cấp'}", cname)
        html_body = html_body.replace("{customer_phone or 'Chưa cung cấp'}", cphone)
        html_body = html_body.replace("{timestamp or '—'}", ts)
        html_body = html_body.replace('{customer_phone}', customer_phone or '')
        html_body = html_body.replace('{customer_name}', customer_name or '')
        html_body = html_body.replace('{timestamp}', ts)
        html_body = html_body.replace("{internal_note or 'Chưa có ghi chú'}", internal_note_val or 'Chưa có ghi chú')
        html_body = html_body.replace('{internal_note}', internal_note_val)
        html_body = html_body.replace('{issue_summary}', issue_val)
        html_body = html_body.replace('{ initials }', initials)

        # --- Thiết lập và gửi email ---
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_user
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        success_msg = f"Đã gửi email thông báo thành công đến {recipient_email}."
        logger.success(success_msg)
        return success_msg

    except Exception as e:
        error_msg = f"Lỗi không xác định khi gửi email: {e}"
        logger.error(error_msg)
        return error_msg