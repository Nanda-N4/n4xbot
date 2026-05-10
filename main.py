import logging
import json
import os
import asyncio
import traceback
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
    "payments": {},
    "categories": {"cat_menu_vip": "🚀 VIP PRO", "cat_menu_sg": "🇸🇬 Singapore", "cat_menu_jp": "🇯🇵 Japan", "cat_menu_sl": "📡 Starlink"}
})

# States
(A_P_NAME, A_P_PRICE, A_P_DESC, A_P_CAT, E_WELCOME, A_PAY_NAME, A_PAY_INFO, A_PAY_QR) = range(8)

# --- Error Handler (Admin ဆီ Error ပို့ရန်) ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    error_message = (
        f"⚠️ <b>Bot Error Occurred!</b>\n\n"
        f"📋 <b>Update:</b> <code>{update}</code>\n\n"
        f"🔍 <b>Traceback:</b>\n<code>{tb_string[-3000:]}</code>"
    )
    
    # Admin ဆီကို Error စာလှမ်းပို့ခြင်း
    await context.bot.send_message(chat_id=config.MY_USER_ID, text=error_message, parse_mode='HTML')

# --- Auto Backup ---
async def send_daily_backup(context: ContextTypes.DEFAULT_TYPE):
    try:
        for file in ['products.json', 'settings.json']:
            if os.path.exists(file):
                await context.bot.send_document(chat_id=config.MY_USER_ID, document=open(file, 'rb'))
    except Exception as e:
        logging.error(f"Backup failed: {e}")

# --- Keyboards ---
async def main_menu():
    keyboard = [[InlineKeyboardButton(name, callback_data=cid)] for cid, name in SETTINGS['categories'].items()]
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

# --- User Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = SETTINGS['welcome_text']
    img = SETTINGS['welcome_img'] or config.IMG_WELCOME
    if img and os.path.exists(img):
        await update.message.reply_photo(photo=open(img, 'rb'), caption=welcome_text, reply_markup=await main_menu(), parse_mode='HTML')
    else:
        await update.message.reply_text(welcome_text, reply_markup=await main_menu(), parse_mode='HTML')

# --- Callback Actions ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith('cat_menu_'):
        keyboard = [[InlineKeyboardButton(f"{p['name']} - {p['price']}", callback_data=f"v_{p_id}")] for p_id, p in PRODUCTS.items() if p['category'] == data]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_caption(caption="📦 <b>ပစ္စည်းရွေးချယ်ပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('v_'):
        p_id = data.replace('v_', '')
        p = PRODUCTS[p_id]
        caption = f"📦 <b>{p['name']}</b>\n💰 စျေးနှုန်း: {p['price']}\n\n{p.get('desc', '-')}"
        keyboard = [[InlineKeyboardButton("🛒 ဝယ်မည်", callback_data=f"ps_{p_id}")], [InlineKeyboardButton("🔙 Back", callback_data=p['category'])]]
        await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('ps_'):
        p_id = data.replace('ps_', '')
        keyboard = []
        if not SETTINGS['payments']:
            keyboard.append([InlineKeyboardButton("👨‍💻 Admin ထံ တိုက်ရိုက်မေးပါ", url=config.ADMIN_LINK)])
        else:
            for pay_id, pay in SETTINGS['payments'].items():
                keyboard.append([InlineKeyboardButton(pay['name'], callback_data=f"sp_{pay_id[-4:]}_{p_id[-4:]}")])
                context.bot_data[f"m_{pay_id[-4:]}"] = pay_id
                context.bot_data[f"m_{p_id[-4:]}"] = p_id
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"v_{p_id}")])
        await query.edit_message_caption(caption="💳 <b>ငွေလွှဲမည့် အကောင့်ရွေးပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('sp_'):
        parts = data.split('_')
        pay_id = context.bot_data.get(f"m_{parts[1]}")
        p_id = context.bot_data.get(f"m_{parts[2]}")
        pay, p = SETTINGS['payments'].get(pay_id), PRODUCTS.get(p_id)
        if pay and p:
            caption = f"✅ <b>Item:</b> {p['name']}\n💰 <b>Price:</b> {p['price']}\n\n{pay['info']}\n\n⚠️ Screenshot ပို့ပေးပါ။"
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=pay['qr'], caption=caption, parse_mode='HTML')
            await query.message.delete()

    # Admin Panel
    elif data == 'adm_manage_p':
        keyboard = [[InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"delp_{pid}")] for pid, p in PRODUCTS.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("📦 <b>ပစ္စည်းစာရင်း</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('delp_'):
        p_id = data.replace('delp_', '')
        if p_id in PRODUCTS: del PRODUCTS[p_id]
        db.save('products.json', PRODUCTS)
        await query.edit_message_text("✅ ဖျက်ပြီးပါပြီ။", reply_markup=admin_home_menu())

    elif data == 'adm_manage_pay':
        keyboard = [[InlineKeyboardButton("➕ အသစ်", callback_data='adm_add_pay_start')]]
        for pay_id, pay in SETTINGS['payments'].items():
            keyboard.append([InlineKeyboardButton(f"🗑 {pay['name']}", callback_data=f"delpay_{pay_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("💳 <b>Payment စီမံရန်</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('delpay_'):
        pay_id = data.replace('delpay_', '')
        if pay_id in SETTINGS['payments']: del SETTINGS['payments'][pay_id]
        db.save('settings.json', SETTINGS)
        await query.edit_message_text("✅ ဖျက်ပြီးပါပြီ။", reply_markup=admin_home_menu())

    elif data == 'adm_back_home':
        await query.edit_message_text("🛠 <b>Admin Panel</b>", reply_markup=admin_home_menu(), parse_mode='HTML')

    elif data == 'adm_close':
        await query.message.delete()

    elif data == 'back_main':
        await query.edit_message_caption(caption=SETTINGS['welcome_text'], reply_markup=await main_menu(), parse_mode='HTML')

# --- Admin Conversations ---
async def add_p_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✨ <b>ပစ္စည်းအမည် ပို့ပါ</b>")
    return A_P_NAME

async def add_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['n'] = update.message.text
    await update.message.reply_text("💰 <b>စျေးနှုန်း ပို့ပါ</b>")
    return A_P_PRICE

async def add_p_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pr'] = update.message.text
    await update.message.reply_text("📖 <b>Detail ပို့ပါ</b>")
    return A_P_DESC

async def add_p_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['d'] = update.message.text
    keyboard = [[InlineKeyboardButton(name, callback_data=cid)] for cid, name in SETTINGS['categories'].items()]
    await update.message.reply_text("📂 <b>Category ရွေးပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return A_P_CAT

async def add_p_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = f"p_{int(datetime.now().timestamp())}"
    PRODUCTS[pid] = {"name": context.user_data['n'], "price": context.user_data['pr'], "desc": context.user_data['d'], "category": update.callback_query.data, "is_available": True}
    db.save('products.json', PRODUCTS)
    await update.callback_query.message.reply_text("✅ ထည့်ပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def welcome_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📝 <b>Welcome စာအသစ် ပို့ပါ</b>")
    return E_WELCOME

async def welcome_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SETTINGS['welcome_text'] = update.message.text
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ ပြင်ပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💳 <b>Payment နာမည်</b>")
    return A_PAY_NAME

async def add_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pn'] = update.message.text
    await update.message.reply_text("📞 <b>အချက်အလက်</b>")
    return A_PAY_INFO

async def add_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pi'] = update.message.text
    await update.message.reply_text("📸 <b>QR ပုံပို့ပါ</b>")
    return A_PAY_QR

async def add_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay_id = f"pay_{int(datetime.now().timestamp())}"
    SETTINGS['payments'][pay_id] = {"name": context.user_data['pn'], "info": context.user_data['pi'], "qr": update.message.photo[-1].file_id}
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ ထည့်ပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

# --- Run Bot ---
async def run_bot():
    app = Application.builder().token(config.TOKEN).build()
    
    # Error Handler ထည့်ခြင်း
    app.add_error_handler(error_handler)
    
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
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, lambda u,c: u.message.reply_text("✅ ပြေစာရရှိပါသည်။ Admin စစ်ဆေးနေပါသည်။")))
    
    async with app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(run_bot())
