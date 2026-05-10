import logging
import json
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes, ConversationHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from db_manager import DBManager

# --- Init ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(message)s', level=logging.INFO)
db = DBManager()

PRODUCTS = db.load('products.json', {})
SETTINGS = db.load('settings.json', {
    "welcome_text": "🌟 <b>Nanda VPN Services</b> မှ ကြိုဆိုပါတယ် 🌟",
    "welcome_img": None,
    "payments": {}
})

# States
(A_P_NAME, A_P_PRICE, A_P_DESC, A_P_IMG, A_P_CAT, 
 A_PAY_NAME, A_PAY_INFO, A_PAY_QR, E_WELCOME) = range(9)

# --- Auto Backup Shipping ---
async def send_daily_backup(context: ContextTypes.DEFAULT_TYPE):
    files = ['products.json', 'settings.json']
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        for file_name in files:
            if os.path.exists(file_name):
                with open(file_name, 'rb') as f:
                    await context.bot.send_document(chat_id=config.MY_USER_ID, document=InputFile(f), filename=f"Backup_{file_name}")
    except Exception as e:
        logging.error(f"Backup failed: {e}")

# --- Keyboards ---
async def main_menu():
    keyboard = [
        [InlineKeyboardButton("🚀 N4 VIP PRO", callback_data='cat_menu_vip')],
        [InlineKeyboardButton("🇸🇬 Singapore (SG)", callback_data='cat_menu_sg')],
        [InlineKeyboardButton("🇯🇵 Japan (JP)", callback_data='cat_menu_jp')],
        [InlineKeyboardButton("📡 Starlink VIP", callback_data='cat_menu_sl')],
        [InlineKeyboardButton("👨‍💻 Admin နှင့် တိုက်ရိုက်ပြောရန်", url=config.ADMIN_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_home_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Products စီမံ/အသစ်ထည့်", callback_data='adm_manage_p')],
        [InlineKeyboardButton("➕ Product အသစ်ထည့်ရန်", callback_data='adm_add_start')],
        [InlineKeyboardButton("💳 Payments စီမံ/အသစ်ထည့်", callback_data='adm_pay_start')],
        [InlineKeyboardButton("👋 Welcome ပြင်ရန်", callback_data='adm_edit_welcome')],
        [InlineKeyboardButton("❌ Exit Panel", callback_data='adm_close')]
    ])

# --- User Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = SETTINGS['welcome_text']
    img = SETTINGS['welcome_img'] or config.IMG_WELCOME
    try:
        if img and os.path.exists(img):
            await update.message.reply_photo(photo=open(img, 'rb'), caption=welcome_text, reply_markup=await main_menu(), parse_mode='HTML')
        else:
            await update.message.reply_text(welcome_text, reply_markup=await main_menu(), parse_mode='HTML')
    except:
        await update.message.reply_text(welcome_text, reply_markup=await main_menu(), parse_mode='HTML')

# --- Admin Function: Add Product ---
async def add_p_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✨ <b>ပစ္စည်းအသစ်ထည့်ခြင်း</b>\nပစ္စည်းအမည် ရိုက်ပို့ပါ 👇", parse_mode='HTML')
    return A_P_NAME

async def add_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p_name'] = update.message.text
    await update.message.reply_text("💰 စျေးနှုန်း ရိုက်ပို့ပါ 👇")
    return A_P_PRICE

async def add_p_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p_price'] = update.message.text
    await update.message.reply_text("📖 Detail/Instruction ရိုက်ပို့ပါ 👇")
    return A_P_DESC

async def add_p_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p_desc'] = update.message.text
    await update.message.reply_text("📸 Product ပုံပို့ပေးပါ (သို့မဟုတ် /skip)")
    return A_P_IMG

async def add_p_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_p_img'] = update.message.photo[-1].file_id if update.message.photo else None
    keyboard = [[InlineKeyboardButton("VIP", callback_data="cat_menu_vip")], [InlineKeyboardButton("SG", callback_data="cat_menu_sg")],
                [InlineKeyboardButton("JP", callback_data="cat_menu_jp")], [InlineKeyboardButton("SL", callback_data="cat_menu_sl")]]
    await update.message.reply_text("📂 Category ရွေးချယ်ပါ 👇", reply_markup=InlineKeyboardMarkup(keyboard))
    return A_P_CAT

async def add_p_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    p_id = f"p_{len(PRODUCTS)+1}"
    PRODUCTS[p_id] = {
        "name": context.user_data['new_p_name'], "price": context.user_data['new_p_price'],
        "desc": context.user_data['new_p_desc'], "img": context.user_data['new_p_img'],
        "category": query.data, "is_available": True
    }
    db.save('products.json', PRODUCTS)
    await query.message.reply_text("✅ ပစ္စည်းအသစ် ထည့်သွင်းပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

# --- Callback Handler ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith('cat_'):
        keyboard = []
        for p_id, p in PRODUCTS.items():
            if p['category'] == data:
                status = "✅" if p['is_available'] else "❌"
                keyboard.append([InlineKeyboardButton(f"{status} {p['name']} - {p['price']}", callback_data=f"view_{p_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_caption(caption="📦 <b>ပစ္စည်းရွေးချယ်ပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('view_'):
        p_id = data.replace('view_', '')
        p = PRODUCTS[p_id]
        caption = f"📦 <b>{p['name']}</b>\n💰 စျေးနှုန်း: {p['price']}\n\n{p['desc']}"
        keyboard = [[InlineKeyboardButton("🛒 ဝယ်ယူမည်", callback_data=f"select_pay_{p_id}")], [InlineKeyboardButton("🔙 Back", callback_data=p['category'])]]
        if p['img']: await query.message.reply_photo(photo=p['img'], caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        else: await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == 'back_main':
        await query.edit_message_caption(caption=SETTINGS['welcome_text'], reply_markup=await main_menu(), parse_mode='HTML')

    elif data == 'adm_close':
        await query.message.delete()

# --- Main Logic Fix ---
async def run_bot():
    app = Application.builder().token(config.TOKEN).build()
    
    # Scheduler Setup
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_backup, 'cron', hour=0, minute=0, args=[app])
    scheduler.start()

    # Admin Conversations
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_p_start, pattern="^adm_add_start$")],
        states={
            A_P_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_name)],
            A_P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_price)],
            A_P_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_desc)],
            A_P_IMG: [MessageHandler(filters.PHOTO | filters.Regex('/skip'), add_p_img)],
            A_P_CAT: [CallbackQueryHandler(add_p_final, pattern="^cat_menu_")]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u,c: u.message.reply_text("🛠 Admin Panel", reply_markup=admin_home_menu()) if u.effective_user.id == config.MY_USER_ID else None))
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    
    print("🚀 N4XBOT is running successfully...")
    
    # Correct way to run polling inside the event loop
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        # Keep the bot alive
        while True:
            await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemError):
        pass
