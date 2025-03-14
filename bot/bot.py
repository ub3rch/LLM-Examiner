import logging
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

USERS_DB = {}
CHOOSING, REGISTER_NAME, REGISTER_PASS, LOGIN_NAME, LOGIN_PASS, AUTHORIZED, UPLOAD_PDF = range(7)

# Клавиатуры
main_keyboard = ReplyKeyboardMarkup([["Регистрация", "Вход"]], one_time_keyboard=True)
auth_keyboard = ReplyKeyboardMarkup([["Отправить PDF", "Выход"]], one_time_keyboard=True)

async def start(update: Update, context: CallbackContext) -> int:
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

# Логика регистрации
async def register_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text
    if name in USERS_DB:
        await update.message.reply_text("Имя занято! Введите другое:")
        return REGISTER_NAME
    context.user_data["reg_name"] = name
    await update.message.reply_text("Придумайте пароль:")
    return REGISTER_PASS

async def register_pass(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    name = context.user_data["reg_name"]
    USERS_DB[name] = password
    await show_auth_menu(update, f"Регистрация успешна, {name}!")
    return AUTHORIZED

# Логика входа
async def login_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text
    if name not in USERS_DB:
        await update.message.reply_text("Пользователь не найден! Введите имя:")
        return LOGIN_NAME
    context.user_data["login_name"] = name
    await update.message.reply_text("Введите пароль:")
    return LOGIN_PASS

async def login_pass(update: Update, context: CallbackContext) -> int:
    password = update.message.text
    name = context.user_data["login_name"]
    if USERS_DB.get(name) == password:
        await show_auth_menu(update, f"Добро пожаловать, {name}!")
        return AUTHORIZED
    await update.message.reply_text("Неверный пароль! Попробуйте снова:")
    return LOGIN_PASS

# Меню авторизованного пользователя
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

# Логика работы с PDF
async def upload_pdf(update: Update, context: CallbackContext) -> int:
    if document := update.message.document:
        if document.mime_type == "application/pdf":
            file = await context.bot.get_file(document.file_id)
            await file.download_to_drive(f"{document.file_id}.pdf")
            await update.message.reply_text("Файл сохранён!", reply_markup=auth_keyboard)
            return AUTHORIZED
    await update.message.reply_text("Отправьте PDF файл:", reply_markup=auth_keyboard)
    return UPLOAD_PDF

async def cancel(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    await update.message.reply_text("Сессия сброшена.", reply_markup=main_keyboard)
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token("7266424537:AAG7T8KReTaDvxsYq84FZuZce6L1nwwg7S0").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_pass)],
            LOGIN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_name)],
            LOGIN_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_pass)],
            AUTHORIZED: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_actions)],
            UPLOAD_PDF: [MessageHandler(filters.Document.ALL, upload_pdf)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()