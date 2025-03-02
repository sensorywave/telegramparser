from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackContext

API_KEY = '7857735611:AAGbtOLVo_yIeG1-yB3E77b7rTzowg58RyI'
app_url = "https://9b7f-109-110-91-207.ngrok-free.app"  # Замените на ваш сервер

application = Application.builder().token(API_KEY).build()

# 📌 Команда /admin открывает Mini App
async def admin(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Открыть админ-панель", web_app=WebAppInfo(url=app_url))]
    ]
    
    await update.message.reply_text("💼 Админ-панель:", reply_markup=InlineKeyboardMarkup(keyboard))

# 📌 Запуск бота
application.add_handler(CommandHandler("admin", admin))

if __name__ == "__main__":  
    application.run_polling()