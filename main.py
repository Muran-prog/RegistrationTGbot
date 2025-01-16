#The main bot file where handlers, handlers and so on are located

import asyncio
import logging
import re
import dns.resolver
import phonenumbers
from email_validator import validate_email, EmailNotValidError
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import sys
from database import Database
from verification import Verification
import sqlite3

# Enable logging
logging.basicConfig(level=logging.INFO)

# Bot token from @BotFather
BOT_TOKEN = ""

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Initialize database and verification
db = Database('shop_bot.db')
verification = Verification()

# States
class RegistrationStates(StatesGroup):
    WAITING_NAME = State()
    WAITING_CONTACT = State()
    WAITING_PASSWORD = State()
    WAITING_PASSWORD_CONFIRM = State()
    WAITING_VERIFICATION = State()

def get_registration_keyboard(user_data: dict = None) -> InlineKeyboardMarkup:
    """Create registration keyboard with user data if available"""
    if user_data is None:
        user_data = {}
    
    buttons = [
        InlineKeyboardButton(
            text=f"Имя: {user_data.get('name', 'Не указано')}" if 'name' in user_data else "Имя",
            callback_data="reg_name"
        ),
        InlineKeyboardButton(
            text=f"Почта / Номер: {user_data.get('contact', 'Не указано')}" if 'contact' in user_data else "Почта / Номер",
            callback_data="reg_contact"
        ),
        InlineKeyboardButton(
            text="Пароль: " + ("●" * len(user_data.get('password', '')) if user_data.get('password') else "Не указан"),
            callback_data="reg_password"
        ),
        InlineKeyboardButton(
            text="Подтвердите пароль: " + ("●" * len(user_data.get('password_confirm', '')) if user_data.get('password_confirm') else "Не указан"),
            callback_data="reg_password_confirm"
        )
    ]
    
    # Add "Готово" button only if all fields are filled
    if all(field in user_data for field in ['name', 'contact', 'password', 'password_confirm']):
        buttons.append(InlineKeyboardButton(text="Готово", callback_data="reg_complete"))
    
    keyboard = []
    for button in buttons:
        keyboard.append([button])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def is_valid_phone(phone: str) -> tuple[bool, str]:
    """
    Validate phone number and check if it exists
    Returns: (is_valid, error_message)
    """
    # Паттерн для проверки украинского номера телефона
    pattern = r'^(?:\+?38)?0\d{9}$'
    if not re.match(pattern, phone):
        return False, "Неверный формат номера телефона"
    
    try:
        # Нормализуем номер телефона
        if not phone.startswith('+'):
            if phone.startswith('38'):
                phone = '+' + phone
            else:
                phone = '+38' + phone
        
        # Парсим номер
        phone_number = phonenumbers.parse(phone)
        
        # Проверяем регион (должен быть Украина)
        if phonenumbers.region_code_for_number(phone_number) != 'UA':
            return False, "Номер телефона должен быть украинским"
        
        # Проверяем, существует ли такой номер
        if not phonenumbers.is_valid_number(phone_number):
            return False, "Такой номер телефона не существует"
        
        # Проверяем, является ли номер мобильным
        if phonenumbers.number_type(phone_number) != phonenumbers.PhoneNumberType.MOBILE:
            return False, "Номер телефона должен быть мобильным"
        
        # Проверяем возможность существования номера
        if not phonenumbers.is_possible_number(phone_number):
            return False, "Номер телефона не может существовать в указанном регионе"
        
        return True, ""
    except Exception as e:
        return False, "Ошибка при проверке номера телефона"

def is_valid_email(email: str) -> tuple[bool, str]:
    """
    Validate email and check if domain exists
    Returns: (is_valid, error_message)
    """
    try:
        # Базовая валидация email с проверкой доставки
        validation = validate_email(email, check_deliverability=True)
        email = validation.normalized
        
        # Получаем домен
        domain = email.split('@')[1]
        
        try:
            # Проверяем существование MX-записей для домена
            mx_records = dns.resolver.resolve(domain, 'MX')
            if not list(mx_records):
                return False, "Домен не принимает почту (нет MX-записей)"
            
            # Проверяем существование A-записи
            try:
                dns.resolver.resolve(domain, 'A')
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                try:
                    dns.resolver.resolve(domain, 'AAAA')
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    return False, "Домен не существует (нет A или AAAA записей)"
            
            return True, ""
        except dns.resolver.NXDOMAIN:
            return False, "Домен email не существует"
        except dns.resolver.NoAnswer:
            return False, "Домен email не настроен корректно"
        except Exception as e:
            return False, f"Ошибка при проверке домена email: {str(e)}"
            
    except EmailNotValidError as e:
        return False, f"Неверный формат email: {str(e)}"
    except Exception as e:
        return False, f"Ошибка при проверке email: {str(e)}"

def is_valid_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength
    Returns: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    if not has_upper:
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    if not has_lower:
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    if not has_digit:
        return False, "Пароль должен содержать хотя бы одну цифру"
    if not has_special:
        return False, "Пароль должен содержать хотя бы один специальный символ"
    
    return True, ""

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Handle the /start command"""
    user_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    if not db.user_exists(user_id):
        # Если пользователь не существует, создаем его
        db.create_user(user_id)
    
    # Проверяем статус блокировки
    if db.is_blocked(user_id):
        # Если пользователь заблокирован
        await message.answer(
            "❌ Ваш аккаунт заблокирован!\n"
            "Обратитесь в поддержку для разблокировки."
        )
        return
    
    # Проверяем авторизацию пользователя
    if db.check_auth(user_id):
        # Обновляем время последнего входа
        db.update_last_login(user_id)
        await message.answer("Привет еще раз!")
    else:
        # Если пользователь не авторизован и не заблокирован, начинаем регистрацию
        await message.answer(
            "Здравствуйте! Для продолжения пользования ботом, пожалуйста, зарегистрируйтесь!",
            reply_markup=get_registration_keyboard()
        )

@dp.callback_query(lambda c: c.data.startswith('reg_'))
async def registration_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Handle registration callbacks"""
    action = callback_query.data[4:]  # Remove 'reg_' prefix
    user_data = await state.get_data()
    
    try:
        if action == "back":
            # Получаем ID сообщений об ошибках
            error_message_ids = user_data.get('error_message_ids', [])
            
            # Удаляем все сообщения об ошибках
            for error_id in error_message_ids:
                try:
                    await callback_query.bot.delete_message(callback_query.message.chat.id, error_id)
                except:
                    pass
            
            # Очищаем список ID сообщений об ошибках
            await state.update_data(error_message_ids=[])
            
            # Возвращаемся в меню регистрации
            await state.set_state(None)
            
            # Проверяем, есть ли уже заполненные поля
            has_filled_fields = any(key in user_data for key in ['name', 'contact', 'password', 'password_confirm'])
            
            message_text = (
                "Пожалуйста, заполните оставшиеся поля:"
                if has_filled_fields else
                "Здравствуйте! Для продолжения пользования ботом, пожалуйста, зарегистрируйтесь!"
            )
            
            await callback_query.message.edit_text(
                message_text,
                reply_markup=get_registration_keyboard(user_data)
            )
        elif action == "use_current_phone":
            # Создаем клавиатуру с кнопкой для отправки контакта
            contact_keyboard = types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="Отправить номер телефона", request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            # Отправляем сообщение с кнопкой для отправки контакта
            contact_message = await callback_query.message.answer(
                "Нажмите на кнопку ниже, чтобы отправить свой номер телефона:",
                reply_markup=contact_keyboard
            )
            
            # Сохраняем ID сообщения с кнопкой
            last_messages = user_data.get('last_messages', [])
            last_messages.append(contact_message.message_id)
            await state.update_data(last_messages=last_messages)
            await callback_query.answer()
            return
        elif action == "name":
            # Имя можно заполнять в любой момент
            await state.set_state(RegistrationStates.WAITING_NAME)
            message_text = (
                "Хотите изменить имя? Введите новое значение:" 
                if 'name' in user_data else 
                "Пожалуйста, напишите, как мы можем к вам обращаться?"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="« Назад", callback_data="reg_back")
            ]])
            new_message = await callback_query.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            await state.update_data(bot_message_id=new_message.message_id)
        elif action == "contact":
            # Проверяем, заполнено ли имя
            if 'name' not in user_data:
                await callback_query.answer("❌ Сначала укажите имя!", show_alert=True)
                return
            await state.set_state(RegistrationStates.WAITING_CONTACT)
            message_text = (
                "Хотите изменить контактные данные? Введите новое значение:" 
                if 'contact' in user_data else 
                "Пожалуйста, укажите ваш контактный номер или email:"
            )
            
            # Создаем инлайн клавиатуру с кнопками
            inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Использовать текущий номер", callback_data="reg_use_current_phone")],
                [InlineKeyboardButton(text="« Назад", callback_data="reg_back")]
            ])
            
            # Отправляем сообщение
            new_message = await callback_query.message.edit_text(
                message_text,
                reply_markup=inline_keyboard
            )
            
            # Сохраняем ID сообщения
            await state.update_data(bot_message_id=new_message.message_id)
        elif action == "password":
            # Проверяем, заполнены ли предыдущие поля
            if 'name' not in user_data:
                await callback_query.answer("❌ Сначала укажите имя!", show_alert=True)
                return
            if 'contact' not in user_data:
                await callback_query.answer("❌ Сначала укажите контактные данные!", show_alert=True)
                return
            await state.set_state(RegistrationStates.WAITING_PASSWORD)
            message_text = (
                "Хотите изменить пароль? Введите новое значение:" 
                if 'password' in user_data else 
                "Пожалуйста, введите пароль:"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="« Назад", callback_data="reg_back")
            ]])
            new_message = await callback_query.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            await state.update_data(bot_message_id=new_message.message_id)
        elif action == "password_confirm":
            # Проверяем, заполнены ли предыдущие поля
            if 'name' not in user_data:
                await callback_query.answer("❌ Сначала укажите имя!", show_alert=True)
                return
            if 'contact' not in user_data:
                await callback_query.answer("❌ Сначала укажите контактные данные!", show_alert=True)
                return
            if 'password' not in user_data:
                await callback_query.answer("❌ Сначала введите пароль!", show_alert=True)
                return
            await state.set_state(RegistrationStates.WAITING_PASSWORD_CONFIRM)
            message_text = (
                "Хотите изменить подтверждение пароля? Введите новое значение:" 
                if 'password_confirm' in user_data else 
                "Пожалуйста, подтвердите пароль:"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="« Назад", callback_data="reg_back")
            ]])
            new_message = await callback_query.message.edit_text(
                message_text,
                reply_markup=keyboard
            )
            await state.update_data(bot_message_id=new_message.message_id)
        elif action == "complete":
            user_data = await state.get_data()
            if user_data['password'] != user_data['password_confirm']:
                await callback_query.answer("Пароли не совпадают!", show_alert=True)
                return
            
            # Generate verification code
            code = verification.generate_code()
            await state.update_data(verification_code=code)
            
            contact = user_data['contact']
            success = False
            
            # Determine contact type and send code
            if '@' in contact:
                # Send email verification
                success = verification.send_email_code(contact, code)
                message = "Мы отправили код подтверждения на ваш email."
            else:
                # Send SMS verification
                success = verification.send_sms_code(contact, code)
                message = "Мы отправили код подтверждения в SMS."
            
            if success:
                await state.set_state(RegistrationStates.WAITING_VERIFICATION)
                new_message = await callback_query.message.edit_text(
                    f"{message}\n\nПожалуйста, введите полученный 6-значный код:"
                )
                # Сохраняем ID сообщения с запросом кода
                await state.update_data(bot_message_id=new_message.message_id)
            else:
                await callback_query.answer(
                    "Ошибка отправки кода подтверждения. Попробуйте позже.",
                    show_alert=True
                )
        
        # Отвечаем на callback query в конце обработки
        try:
            await callback_query.answer()
        except Exception as e:
            logging.warning(f"Failed to answer callback query: {e}")
            
    except Exception as e:
        logging.error(f"Error in registration callback: {e}")
        try:
            await callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
        except:
            pass

@dp.message(RegistrationStates.WAITING_NAME)
async def process_name(message: types.Message, state: FSMContext):
    """Process user's name input"""
    # Получаем данные состояния
    state_data = await state.get_data()
    bot_message_id = state_data.get('bot_message_id')
    error_message_ids = state_data.get('error_message_ids', [])
    current_name = state_data.get('name')
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    # Проверяем, не совпадает ли с текущим значением
    if current_name and message.text.strip() == current_name:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            "❌ Вы ввели то же самое имя!\n\n"
            "Пожалуйста, введите другое значение или вернитесь назад.",
            show_alert=True
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Если значение новое, удаляем все предыдущие сообщения об ошибках
    for error_id in error_message_ids:
        try:
            await message.bot.delete_message(message.chat.id, error_id)
        except:
            pass
    
    # Удаляем предыдущее сообщение бота с запросом
    if bot_message_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_message_id)
        except:
            pass
    
    # Очищаем список ID сообщений об ошибках
    await state.update_data(error_message_ids=[])
    
    await state.update_data(name=message.text)
    user_data = await state.get_data()
    
    # Отправляем новое сообщение и сохраняем его ID
    new_message = await message.answer(
        "Пожалуйста, заполните оставшиеся поля:",
        reply_markup=get_registration_keyboard(user_data)
    )
    await state.update_data(bot_message_id=new_message.message_id)

@dp.message(RegistrationStates.WAITING_CONTACT)
async def process_contact(message: types.Message, state: FSMContext):
    """Process user's contact input"""
    # Получаем данные состояния
    state_data = await state.get_data()
    bot_message_id = state_data.get('bot_message_id')
    error_message_ids = state_data.get('error_message_ids', [])
    current_contact = state_data.get('contact')
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    # Проверяем тип сообщения
    if message.contact:
        # Если это контакт, получаем номер телефона
        contact = message.contact.phone_number
        if not contact.startswith('+'):
            contact = '+' + contact
    else:
        # Если это текстовое сообщение
        if not message.text:
            return
        contact = message.text.strip()
    
    # Проверяем, не совпадает ли с текущим значением
    if current_contact and contact == current_contact:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            "❌ Вы ввели те же контактные данные!\n\n"
            "Пожалуйста, введите другое значение или вернитесь назад."
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Проверяем валидность введенных данных
    is_valid = False
    error_msg = ""
    
    # Пробуем как телефон
    is_valid_phone_result, phone_error = is_valid_phone(contact)
    if is_valid_phone_result:
        is_valid = True
    else:
        # Если не телефон, пробуем как email
        is_valid_email_result, email_error = is_valid_email(contact)
        if is_valid_email_result:
            is_valid = True
        else:
            error_msg = (
                "❌ Введенные данные некорректны!\n\n"
                f"Ошибка проверки телефона: {phone_error}\n"
                f"Ошибка проверки email: {email_error}\n\n"
                "Пожалуйста, введите:\n"
                "- Корректный email (например: example@email.com)\n"
                "- Или номер телефона в формате: +380xxxxxxxxx, 380xxxxxxxxx, 0xxxxxxxxx"
            )
    
    if not is_valid:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            error_msg
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Если данные валидны, удаляем все предыдущие сообщения об ошибках
    for error_id in error_message_ids:
        try:
            await message.bot.delete_message(message.chat.id, error_id)
        except:
            pass
    
    # Удаляем предыдущее сообщение бота с запросом
    if bot_message_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_message_id)
        except:
            pass
    
    # Удаляем сообщение с кнопкой "Отправить номер"
    last_messages = state_data.get('last_messages', [])
    for msg_id in last_messages:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except:
            pass
    
    # Очищаем список ID сообщений об ошибках
    await state.update_data(error_message_ids=[])
    
    await state.update_data(contact=contact)
    user_data = await state.get_data()
    
    # Отправляем новое сообщение и сохраняем его ID
    new_message = await message.answer(
        "Пожалуйста, заполните оставшиеся поля:",
        reply_markup=get_registration_keyboard(user_data)
    )
    await state.update_data(bot_message_id=new_message.message_id)

@dp.message(RegistrationStates.WAITING_PASSWORD)
async def process_password(message: types.Message, state: FSMContext):
    """Process user's password input"""
    # Получаем данные состояния
    state_data = await state.get_data()
    bot_message_id = state_data.get('bot_message_id')
    error_message_ids = state_data.get('error_message_ids', [])
    current_password = state_data.get('password')
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    # Проверяем, не совпадает ли с текущим значением
    if current_password and message.text == current_password:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            "❌ Вы ввели тот же пароль!\n\n"
            "Пожалуйста, введите другой пароль или вернитесь назад."
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Проверяем сложность пароля
    is_valid, error_message = is_valid_password(message.text)
    if not is_valid:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            f"❌ Пароль слишком слабый!\n\n{error_message}\n\n"
            "Требования к паролю:\n"
            "- Минимум 8 символов\n"
            "- Хотя бы одна заглавная буква\n"
            "- Хотя бы одна строчная буква\n"
            "- Хотя бы одна цифра\n"
            "- Хотя бы один специальный символ"
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Если пароль валидный, удаляем все предыдущие сообщения об ошибках
    for error_id in error_message_ids:
        try:
            await message.bot.delete_message(message.chat.id, error_id)
        except:
            pass
    
    # Удаляем предыдущее сообщение бота с запросом
    if bot_message_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_message_id)
        except:
            pass
    
    # Очищаем список ID сообщений об ошибках
    await state.update_data(error_message_ids=[])
    
    # Сохраняем новый пароль и сбрасываем подтверждение пароля
    await state.update_data(password=message.text, password_confirm=None)
    user_data = await state.get_data()
    
    # Отправляем новое сообщение и сохраняем его ID
    new_message = await message.answer(
        "Пожалуйста, заполните оставшиеся поля:",
        reply_markup=get_registration_keyboard(user_data)
    )
    await state.update_data(bot_message_id=new_message.message_id)

@dp.message(RegistrationStates.WAITING_PASSWORD_CONFIRM)
async def process_password_confirm(message: types.Message, state: FSMContext):
    """Process user's password confirmation input"""
    # Получаем данные состояния
    state_data = await state.get_data()
    bot_message_id = state_data.get('bot_message_id')
    error_message_ids = state_data.get('error_message_ids', [])
    current_password_confirm = state_data.get('password_confirm')
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    # Проверяем, не совпадает ли с текущим значением подтверждения
    if current_password_confirm and message.text == current_password_confirm:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            "❌ Вы ввели то же подтверждение пароля!\n\n"
            "Пожалуйста, введите другое значение или вернитесь назад.",
            show_alert=True
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Проверяем совпадение паролей
    password = state_data.get('password', '')
    if message.text != password:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            "❌ Пароли не совпадают!\n\n"
            "Пожалуйста, введите пароль повторно.",
            show_alert=True
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Если пароли совпадают, удаляем все предыдущие сообщения об ошибках
    for error_id in error_message_ids:
        try:
            await message.bot.delete_message(message.chat.id, error_id)
        except:
            pass
    
    # Удаляем предыдущее сообщение бота с запросом
    if bot_message_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_message_id)
        except:
            pass
    
    # Очищаем список ID сообщений об ошибках
    await state.update_data(error_message_ids=[])
    
    await state.update_data(password_confirm=message.text)
    user_data = await state.get_data()
    
    # Отправляем новое сообщение и сохраняем его ID
    new_message = await message.answer(
        "Пожалуйста, заполните оставшиеся поля:",
        reply_markup=get_registration_keyboard(user_data)
    )
    await state.update_data(bot_message_id=new_message.message_id)

@dp.message(RegistrationStates.WAITING_VERIFICATION)
async def process_verification(message: types.Message, state: FSMContext):
    """Process verification code input"""
    # Получаем данные состояния
    state_data = await state.get_data()
    verification_code = state_data.get('verification_code')
    bot_message_id = state_data.get('bot_message_id')
    error_message_ids = state_data.get('error_message_ids', [])
    attempts = state_data.get('verification_attempts', 0)
    
    # Удаляем сообщение пользователя
    await message.delete()
    
    # Проверяем количество попыток
    if attempts >= 5:
        # Блокируем пользователя
        db.block_user(message.from_user.id)
        
        # Удаляем все предыдущие сообщения об ошибках
        for error_id in error_message_ids:
            try:
                await message.bot.delete_message(message.chat.id, error_id)
            except:
                pass
        
        # Удаляем предыдущее сообщение бота с запросом кода
        if bot_message_id:
            try:
                await message.bot.delete_message(message.chat.id, bot_message_id)
            except:
                pass
        
        # Отправляем сообщение о блокировке
        await message.answer(
            "❌ Вы превысили максимальное количество попыток ввода кода!\n"
            "Ваш аккаунт заблокирован. Обратитесь в поддержку."
        )
        
        # Очищаем состояние
        await state.clear()
        return
    
    # Проверяем код
    if message.text.strip() != verification_code:
        # Увеличиваем счетчик попыток
        attempts += 1
        await state.update_data(verification_attempts=attempts)
        
        # Отправляем сообщение об ошибке с указанием оставшихся попыток
        remaining_attempts = 5 - attempts
        error_message = await message.answer(
            f"❌ Неверный код подтверждения!\n\n"
            f"Осталось попыток: {remaining_attempts}\n"
            "Пожалуйста, проверьте код и попробуйте снова.",
            show_alert=True
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Если код верный, удаляем все предыдущие сообщения об ошибках
    for error_id in error_message_ids:
        try:
            await message.bot.delete_message(message.chat.id, error_id)
        except:
            pass
    
    # Удаляем предыдущее сообщение бота с запросом кода
    if bot_message_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_message_id)
        except:
            pass
    
    # Очищаем список ID сообщений об ошибках
    await state.update_data(error_message_ids=[])
    
    # Код верный, завершаем регистрацию
    user_id = message.from_user.id
    db.update_user_field(user_id, 'name', state_data['name'])
    db.update_user_field(user_id, 'contact', state_data['contact'])
    db.update_user_field(user_id, 'password', state_data['password'])
    db.complete_registration(user_id)
    
    # Clear state and show welcome message
    await state.clear()
    await message.answer("Привет! Вы успешно зарегистрировались!")

# Этот обработчик должен быть последним, чтобы не перехватывать команды
@dp.message(F.text)
async def delete_unexpected_messages(message: types.Message, state: FSMContext):
    """Delete messages that are sent when bot is not expecting input"""
    current_state = await state.get_state()
    
    # Если нет активного состояния или оно не в списке ожидания ввода
    if current_state not in [
        RegistrationStates.WAITING_NAME.state,
        RegistrationStates.WAITING_CONTACT.state,
        RegistrationStates.WAITING_PASSWORD.state,
        RegistrationStates.WAITING_PASSWORD_CONFIRM.state,
        RegistrationStates.WAITING_VERIFICATION.state
    ]:
        await message.delete()
        return  # Важно! Прерываем выполнение, чтобы не срабатывали другие обработчики

# Добавляем новый обработчик для получения контакта
@dp.message(RegistrationStates.WAITING_CONTACT, F.contact)
async def process_contact_button(message: types.Message, state: FSMContext):
    """Process contact shared via button"""
    # Получаем данные состояния
    state_data = await state.get_data()
    bot_message_id = state_data.get('bot_message_id')
    error_message_ids = state_data.get('error_message_ids', [])
    current_contact = state_data.get('contact')
    
    # Удаляем сообщение с контактом
    await message.delete()
    
    # Получаем номер телефона
    phone = message.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone
    
    # Проверяем, не совпадает ли с текущим значением
    if current_contact and phone == current_contact:
        # Отправляем сообщение об ошибке
        error_message = await message.answer(
            "❌ Вы ввели тот же номер телефона!\n\n"
            "Пожалуйста, введите другой номер или email, или вернитесь назад.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="« Назад", callback_data="reg_back")
            ]])
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Получаем ID последних сообщений бота
    last_messages = state_data.get('last_messages', [])
    
    # Удаляем сообщение с просьбой нажать на кнопку и само сообщение с кнопкой
    for msg_id in last_messages:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except:
            pass
    
    # Удаляем предыдущее сообщение бота с инлайн кнопками
    if bot_message_id:
        try:
            await message.bot.delete_message(message.chat.id, bot_message_id)
        except:
            pass
    
    # Удаляем предыдущие сообщения об ошибках
    for error_id in error_message_ids:
        try:
            await message.bot.delete_message(message.chat.id, error_id)
        except:
            pass
    
    # Проверяем валидность номера
    is_valid, error_msg = is_valid_phone(phone)
    if not is_valid:
        error_message = await message.answer(
            f"❌ Ваш номер не соответствует требованиям:\n{error_msg}\n\n"
            "Пожалуйста, введите другой номер телефона или email:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="« Назад", callback_data="reg_back")
            ]])
        )
        # Сохраняем ID сообщения об ошибке
        error_message_ids.append(error_message.message_id)
        await state.update_data(error_message_ids=error_message_ids)
        return
    
    # Очищаем список ID сообщений об ошибках
    await state.update_data(error_message_ids=[])
    
    # Если номер валидный, сохраняем его
    await state.update_data(contact=phone)
    user_data = await state.get_data()
    
    # Показываем обновленное меню регистрации
    await message.answer(
        "Пожалуйста, заполните оставшиеся поля:",
        reply_markup=get_registration_keyboard(user_data)
    )

async def main():
    """Main function to start the bot"""
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform == "win32":
        # Настройка для Windows
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
