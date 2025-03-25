import logging
import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackContext,
)

# Настройки
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация API
API_BASE_URL = "http://localhost:8000"
BOT_TOKEN = "7266424537:AAG7T8KReTaDvxsYq84FZuZce6L1nwwg7S0"

# Состояния бота
CHOOSING, REGISTER_NAME, REGISTER_PASS, LOGIN_NAME, LOGIN_PASS, AUTHORIZED, UPLOAD_PDF, FROM_REG_TO_LOG = range(8)

# Клавиатуры
main_keyboard = ReplyKeyboardMarkup([["Регистрация", "Вход"]], one_time_keyboard=True)
auth_keyboard = ReplyKeyboardMarkup([["Отправить PDF", "Выход"]], one_time_keyboard=True)
from_reg_to_log_keyboard = ReplyKeyboardMarkup([["Войти", "Регистрация"]], one_time_keyboard=True)


async def start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard)
    return CHOOSING

async def start_with_command(update: Update, context: CallbackContext) -> int:
    command = update.message.text
    if(command == "Регистрация"):
        await update.message.reply_text("Введите имя для регистрации:")
        return REGISTER_NAME
    elif(command == "Вход"):
        await update.message.reply_text("Введите ваше имя:")
        return LOGIN_NAME
    else:
        await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard)
        return CHOOSING

async def choose_action(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Регистрация":
        await update.message.reply_text("Введите имя для регистрации:")
        return REGISTER_NAME
    elif text == "Вход":
        await update.message.reply_text("Введите ваше имя:")
        return LOGIN_NAME
    await update.message.reply_text("Используйте кнопки!", reply_markup=main_keyboard)
    return CHOOSING

async def register_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text
    context.user_data["reg_name"] = name
    await update.message.reply_text("Придумайте пароль:")
    return REGISTER_PASS

async def register_pass(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    context.user_data["reg_password"] = password
    name = context.user_data["reg_name"]
    print("hehehe")

    try:
        # Отправляем запрос на регистрацию в API
        response = requests.post(
            f"{API_BASE_URL}/user",
            json={"username": name, "hashed_password": password}
        )
        
        if response.status_code == 200:
            await show_auth_menu(update, f"Регистрация успешна, {name}!")
            return AUTHORIZED
        elif response.status_code == 402:
            await update.message.reply_text(f"Пользователь с логином {name} уже существует, хотите войти?", reply_markup=from_reg_to_log_keyboard)
            return FROM_REG_TO_LOG
        else:
            error_msg = response.json().get("detail", "Ошибка регистрации")
            await update.message.reply_text(f"Ошибка: {error_msg}")
            return CHOOSING
    except Exception as e:
        logger.error(f"API error: {e}")
        await update.message.reply_text("Ошибка соединения с сервером. Попробуйте позже.", reply_markup=main_keyboard )
        return CHOOSING

async def login_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text
    context.user_data["login_name"] = name
    await update.message.reply_text("Введите пароль:")
    return LOGIN_PASS

async def login_pass(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    context.user_data["login_password"] = password
    name = context.user_data["login_name"]

    try:
        # Получаем токен от API
        response = requests.post(
            f"{API_BASE_URL}/auth",
            data={"username": name, "password": password, }
        )
        
        if response.status_code == 200:
            token_data = response.json()
            context.user_data["access_token"] = token_data["access_token"]
            await show_auth_menu(update, f"Добро пожаловать, {name}!")
            return AUTHORIZED
        else:
            error_msg = response.json().get("detail", "Неверный логин или пароль")
            await update.message.reply_text(f"Неверный логин или пароль")
            return CHOOSING
    except Exception as e:
        logger.error(f"API error: {e}")
        await update.message.reply_text("Ошибка соединения с сервером. Попробуйте позже.", reply_markup=main_keyboard )
        return CHOOSING

async def from_reg_to_log(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if(text == "Войти"):
        name = context.user_data["reg_name"]
        password = context.user_data["reg_password"]
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth",
                data={"username": name, "password": password, }
            )
            
            if response.status_code == 200:
                token_data = response.json()
                context.user_data["access_token"] = token_data["access_token"]
                await show_auth_menu(update, f"Добро пожаловать, {name}!")
                return AUTHORIZED
            else:
                error_msg = response.json().get("detail", "Неверный логин или пароль")
                await update.message.reply_text(f"Неверный логин или пароль", reply_markup=main_keyboard)
                
                return CHOOSING
        except Exception as e:
            logger.error(f"API error: {e}")
            await update.message.reply_text("Ошибка соединения с сервером. Попробуйте позже.", reply_markup=main_keyboard)
            return CHOOSING
    if(text == "Регистрация"):
        await update.message.reply_text("Введите имя для регистрации:", reply_markup=main_keyboard)
        return REGISTER_NAME
    else:
        await update.message.reply_text("Выберите действие:", reply_markup=main_keyboard)
        return CHOOSING


async def show_auth_menu(update: Update, message: str) -> None:
    await update.message.reply_text(message, reply_markup=auth_keyboard)
    

async def auth_actions(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    if text == "Отправить PDF":
        await update.message.reply_text("Отправьте PDF файл:")
        return UPLOAD_PDF
    elif text == "Выход":
        context.user_data.clear()
        await update.message.reply_text("Вы вышли из системы!", reply_markup=main_keyboard)
        return CHOOSING
    await update.message.reply_text("Используйте кнопки!", reply_markup=auth_keyboard)
    return AUTHORIZED

async def upload_pdf(update: Update, context: CallbackContext) -> int:
    if document := update.message.document:
        if document.mime_type == "application/pdf":
            # Здесь можно добавить загрузку файла на сервер через API
            # Используя context.user_data["access_token"] для аутентификации
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(f"{document.file_id}.pdf")
            await update.message.reply_text("Файл сохранён локально!", reply_markup=auth_keyboard)
            return AUTHORIZED
    await update.message.reply_text("Отправьте PDF файл:", reply_markup=auth_keyboard)
    return UPLOAD_PDF

async def cancel(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text("Сессия сброшена.", reply_markup=main_keyboard)
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT & ~filters.COMMAND, start_with_command)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_pass)],
            LOGIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_name)],
            LOGIN_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_pass)],
            AUTHORIZED: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_actions)],
            UPLOAD_PDF: [MessageHandler(filters.Document.ALL, upload_pdf)],
            FROM_REG_TO_LOG: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_reg_to_log)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()