import os
import time
import json
import gspread
from typing import Literal
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
CREDS_PATH = os.getenv("CREDS_PATH")
WORKSHEET_NAME_ORDER = os.getenv("WORKSHEET_NAME_ORDER")

class OrderSheetLogger:
    def __init__(self):
        self.creds_path = CREDS_PATH
        self.spreadsheet_id = SPREADSHEET_ID
        self.worksheet_name_order = WORKSHEET_NAME_ORDER
        self.client = None
        self.worksheet = None
        self._connect()

    def _connect(self):
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(self.creds_path, scopes=scopes)
        self.client = gspread.authorize(creds)
        sh = self.client.open_by_key(self.spreadsheet_id)
        try:
            self.worksheet = sh.worksheet(self.worksheet_name_order)
        except gspread.exceptions.WorksheetNotFound:
            # nếu worksheet name không tồn tại, tạo mới
            self.worksheet = sh.add_worksheet(title=self.worksheet_name_order, rows="1000", cols="20")

    def log(
        self, 
        order_id: int,
        receiver_name: str,
        receiver_phone_number: str,
        receiver_email: str,
        course_names: str,
        admission_day: str,
        grand_total: float,
        payment: str,
    ):
        
        row = [
            order_id,
            receiver_name,
            receiver_phone_number,
            receiver_email,
            course_names,
            admission_day,
            grand_total,
            payment,
        ]
        try:
            self.worksheet.append_row(row, value_input_option='USER_ENTERED')
        except Exception as e:
            # thử.retry hoặc log lỗi vào file local
            print(f"Error when appending to sheet: {e}")
            # optional: sleep rồi thử lại
            time.sleep(5)
            try:
                self.worksheet.append_row(row, value_input_option='USER_ENTERED')
            except Exception as e2:
                print(f"Second attempt failed: {e2}")