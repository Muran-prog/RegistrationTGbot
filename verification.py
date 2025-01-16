#Secondary bot file which is responsible for sending emails with confirmation code, checking this code, and so on.

import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
import phonenumbers

class Verification:
    def __init__(self):
        # Email configuration
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        # TODO: Replace these values with your Gmail credentials
        self.smtp_username = ""  # Замените на ваш Gmail
        self.smtp_password = ""   # Замените на пароль приложения Gmail (16 символов с пробелами)
        
        # Twilio configuration
        # TODO: Replace with your Twilio credentials
        self.twilio_account_sid = ""
        self.twilio_auth_token = ""
        self.twilio_phone_number = ""  # В формате +1234567890
        
    def generate_code(self) -> str:
        """Generate a 6-digit verification code"""
        return ''.join(random.choices('0123456789', k=6))
    
    def send_email_code(self, email: str, code: str) -> bool:
        """Send verification code via email"""
        try:
            if self.smtp_username == "your.email@gmail.com":
                print("ERROR: Please configure your Gmail credentials in verification.py")
                return False

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = email
            msg['Subject'] = "Код подтверждения"
            
            body = f"""
            Здравствуйте!
            
            Ваш код подтверждения: {code}
            
            Если вы не запрашивали этот код, пожалуйста, проигнорируйте это сообщение.
            
            С уважением,
            Ваш бот
            """
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def send_sms_code(self, phone: str, code: str) -> bool:
        """Send verification code via SMS"""
        try:
            if self.twilio_account_sid == "your_account_sid":
                print("ERROR: Please configure your Twilio credentials in verification.py")
                return False
                
            # Нормализуем номер телефона
            if not phone.startswith('+'):
                if phone.startswith('38'):
                    phone = '+' + phone
                else:
                    phone = '+38' + phone
            
            # Проверяем формат номера
            parsed_number = phonenumbers.parse(phone)
            if not phonenumbers.is_valid_number(parsed_number):
                print("Error: Invalid phone number format")
                return False
            
            # Инициализируем клиент Twilio
            client = Client(self.twilio_account_sid, self.twilio_auth_token)
            
            # Отправляем SMS
            message = client.messages.create(
                body=f"Ваш код подтверждения: {code}\n\nНикому не сообщайте этот код!",
                from_=self.twilio_phone_number,
                to=phone
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending SMS: {e}")
            return False 
