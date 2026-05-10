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

# Load Database
PRODUCTS = db.load('products.json', {})
SETTINGS = db.load('settings.json', {
    "welcome_text": "🌟 <b>Nanda VPN Services</b> မှ ကြိုဆိုပါတယ် 🌟",
    "welcome_img": None,
    "payments": {},
    "categories": {
        "cat_menu_vip": "🚀 VIP PRO", 
        "cat_menu_sg": "🇸🇬 Singapore", 
        "cat_menu_jp": "🇯🇵 Japan", 
        "cat_menu_sl": "📡 Starlink"
    }
})

# States for Admin Conversations
(A_P_NAME, A_P_PRICE, A_P_DESC, A_P_CAT, E_WELCOME, A_PAY_NAME, A_PAY_INFO, A_PAY_QR) = range(8)

# --- Auto Backup Shipping ---
async def send_daily_backup(context: ContextTypes.DEFAULT_TYPE):
    files = ['products.json', 'settings.json']
    try:
        for file_name in files:
            if os.path.exists(file_name):
                with open(file_name, 'rb') as f:
                    await context.bot.send_document(chat_id=config.MY_USER_ID, document=InputFile(f))
    except Exception as e:
        logging.error(f"Backup failed: {e}")

# --- Keyboards ---
async def main_menu():
    keyboard = []
    for cat_id, cat_name in SETTINGS['categories'].items():
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=cat_id)])
    keyboard.append([InlineKeyboardButton("👨‍💻 Admin နှင့် တိုက်ရိုက်ပြောရန်", url=config.ADMIN_LINK)])
    return InlineKeyboardMarkup(keyboard)

def admin_home_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Products စီမံရန်", callback_data='adm_manage_p')],
        [InlineKeyboardButton("➕ ပစ္စည်းအသစ်ထည့်ရန်", callback_data='adm_add_start')],
        [InlineKeyboardButton("💳 Payments စီမံရန်", callback_data='adm_manage_pay')],
        [InlineKeyboardButton("👋 Welcome စာပြင်ရန်", callback_data='adm_edit_welcome')],
        [InlineKeyboardButton("❌ ပိတ်မည်", callback_data='adm_close')]
    ])

# --- User Side Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = SETTINGS['welcome_text']
    img = SETTINGS['welcome_img'] or config.IMG_WELCOME
    if img and os.path.exists(img):
        await update.message.reply_photo(photo=open(img, 'rb'), caption=welcome_text, reply_markup=await main_menu(), parse_mode='HTML')
    else:
        await update.message.reply_text(welcome_text, reply_markup=await main_menu(), parse_mode='HTML')

# --- Callback Action Logic ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # Category View
    if data.startswith('cat_menu_'):
        keyboard = []
        for p_id, p in PRODUCTS.items():
            if p['category'] == data:
                keyboard.append([InlineKeyboardButton(f"{p['name']} - {p['price']}", callback_data=f"view_{p_id}")])
        keyboard.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data='back_main')])
        await query.edit_message_caption(caption="📦 <b>ပစ္စည်းရွေးချယ်ပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # Product Detail View
    elif data.startswith('view_'):
        p_id = data.replace('view_', '')
        p = PRODUCTS[p_id]
        caption = f"📦 <b>{p['name']}</b>\n💰 စျေးနှုန်း: <b>{p['price']}</b>\n\n{p.get('desc', '-')}"
        keyboard = [
            [InlineKeyboardButton("🛒 ဝယ်ယူမည်", callback_data=f"pay_select_{p_id}")],
            [InlineKeyboardButton("🔙 နောက်သို့", callback_data=p['category'])]
        ]
        await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # Payment Selection
    elif data.startswith('pay_select_'):
        p_id = data.replace('pay_select_', '')
        keyboard = []
        if not SETTINGS['payments']:
            keyboard.append([InlineKeyboardButton("👨‍💻 Admin ထံ တိုက်ရိုက်မေးပါ", url=config.ADMIN_LINK)])
        else:
            for pay_id, pay in SETTINGS['payments'].items():
                keyboard.append([InlineKeyboardButton(pay['name'], callback_data=f"spay_{pay_id}_{p_id}")])
        keyboard.append([InlineKeyboardButton("🔙 နောက်သို့", callback_data=f"view_{p_id}")])
        await query.edit_message_caption(caption="💳 <b>ငွေလွှဲမည့် အကောင့်ရွေးပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # Show QR and Payment Info
    elif data.startswith('spay_'):
        parts = data.split('_')
        pay_id, p_id = parts[1], parts[2]
        if pay_id in SETTINGS['payments'] and p_id in PRODUCTS:
            pay = SETTINGS['payments'][pay_id]
            p = PRODUCTS[p_id]
            caption = f"✅ <b>Item:</b> {p['name']}\n💰 <b>Price:</b> {p['price']}\n\n{pay['info']}\n\n⚠️ ငွေလွှဲပြီး Screenshot ပို့ပေးပါ။"
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=pay['qr'], caption=caption, parse_mode='HTML')
            await query.message.delete()

    # Admin Panel: Product Management
    elif data == 'adm_manage_p':
        keyboard = []
        for p_id, p in PRODUCTS.items():
            keyboard.append([InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"adm_delp_{p_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("📦 <b>ပစ္စည်းစာရင်း (ဖျက်ရန် နှိပ်ပါ)</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('adm_delp_'):
        p_id = data.replace('adm_delp_', '')
        if p_id in PRODUCTS: del PRODUCTS[p_id]
        db.save('products.json', PRODUCTS)
        await query.edit_message_text("✅ ပစ္စည်းဖျက်ပြီးပါပြီ။", reply_markup=admin_home_menu())

    # Admin Panel: Payment Management
    elif data == 'adm_manage_pay':
        keyboard = [[InlineKeyboardButton("➕ အကောင့်အသစ်ထည့်", callback_data='adm_add_pay_start')]]
        for pay_id, pay in SETTINGS['payments'].items():
            keyboard.append([InlineKeyboardButton(f"🗑 {pay['name']}", callback_data=f"adm_delpay_{pay_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("💳 <b>Payment စီမံရန်</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('adm_delpay_'):
        pay_id = data.replace('adm_delpay_', '')
        if pay_id in SETTINGS['payments']: del SETTINGS['payments'][pay_id]
        db.save('settings.json', SETTINGS)
        await query.edit_message_text("✅ Payment ဖျက်ပြီးပါပြီ။", reply_markup=admin_home_menu())

    elif data == 'adm_back_home':
        await query.edit_message_text("🛠 <b>Admin Panel</b>", reply_markup=admin_home_menu(), parse_mode='HTML')

    elif data == 'adm_close':
        await query.message.delete()

    elif data == 'back_main':
        await query.edit_message_caption(caption=SETTINGS['welcome_text'], reply_markup=await main_menu(), parse_mode='HTML')

# --- Admin Conversation Logic ---
async def add_p_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✨ <b>ပစ္စည်းအမည် ရိုက်ပို့ပါ</b> 👇", parse_mode='HTML')
    return A_P_NAME

async def add_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_p_name'] = update.message.text
    await update.message.reply_text("💰 <b>စျေးနှုန်း ရိုက်ပို့ပါ</b> 👇", parse_mode='HTML')
    return A_P_PRICE

async def add_p_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_p_price'] = update.message.text
    await update.message.reply_text("📖 <b>Detail/Description ရိုက်ပို့ပါ</b> 👇", parse_mode='HTML')
    return A_P_DESC

async def add_p_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_p_desc'] = update.message.text
    keyboard = []
    for cat_id, cat_name in SETTINGS['categories'].items():
        keyboard.append([InlineKeyboardButton(cat_name, callback_data=cat_id)])
    await update.message.reply_text("📂 <b>Category ရွေးချယ်ပါ</b> 👇", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return A_P_CAT

async def add_p_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    p_id = f"p_{int(datetime.now().timestamp())}"
    PRODUCTS[p_id] = {
        "name": context.user_data['temp_p_name'], "price": context.user_data['temp_p_price'],
        "desc": context.user_data['temp_p_desc'], "category": query.data, "is_available": True
    }
    db.save('products.json', PRODUCTS)
    await query.message.reply_text(f"✅ {PRODUCTS[p_id]['name']} ထည့်သွင်းပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def welcome_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📝 <b>Welcome စာသားအသစ် ပို့ပေးပါ</b>", parse_mode='HTML')
    return E_WELCOME

async def welcome_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SETTINGS['welcome_text'] = update.message.text
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ ပြင်ဆင်ပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💳 <b>Payment နာမည်ပို့ပါ</b> (ဥပမာ - Kpay)")
    return A_PAY_NAME

async def add_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_pay_name'] = update.message.text
    await update.message.reply_text("📞 <b>အကောင့်အချက်အလက် ပို့ပေးပါ</b>")
    return A_PAY_INFO

async def add_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_pay_info'] = update.message.text
    await update.message.reply_text("📸 <b>QR Code ပုံ ပို့ပေးပါ</b>")
    return A_PAY_QR

async def add_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပုံတစ်ပုံ ပို့ပေးပါ။")
        return A_PAY_QR
    pay_id = f"pay_{int(datetime.now().timestamp())}"
    SETTINGS['payments'][pay_id] = {
        "name": context.user_data['temp_pay_name'], "info": context.user_data['temp_pay_info'],
        "qr": update.message.photo[-1].file_id
    }
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ Payment ထည့်သွင်းပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

# --- Run Bot ---
async def run_bot():
    app = Application.builder().token(config.TOKEN).build()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_backup, 'cron', hour=0, minute=0, args=[app])
    scheduler.start()

    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_p_start, pattern="^adm_add_start$"),
            CallbackQueryHandler(welcome_edit_start, pattern="^adm_edit_welcome$"),
            CallbackQueryHandler(add_pay_start, pattern="^adm_add_pay_start$")
        ],
        states={
            A_P_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_name)],
            A_P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_price)],
            A_P_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_desc)],
            A_P_CAT: [CallbackQueryHandler(add_p_final, pattern="^cat_menu_")],
            E_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, welcome_edit_save)],
            A_PAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pay_name)],
            A_PAY_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pay_info)],
            A_PAY_QR: [MessageHandler(filters.PHOTO, add_pay_qr)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", lambda u,c: u.message.reply_text("🛠 Admin Panel", reply_markup=admin_home_menu()) if u.effective_user.id == config.MY_USER_ID else None))
    app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, lambda u,c: u.message.reply_text("✅ ပြေစာ ရရှိပါသည်။ Admin စစ်ဆေးနေပါသည်။")))
    
    print("🚀 N4XBOT Live - No Conflict Mode...")
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass
