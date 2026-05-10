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
    "payments": {},
    "categories": {"c1": "🚀 VIP PRO", "c2": "🇸🇬 Singapore", "c3": "🇯🇵 Japan", "c4": "📡 Starlink"}
})

# States
(A_P_NAME, A_P_PRICE, A_P_DESC, A_P_CAT, E_WELCOME, A_PAY_NAME, A_PAY_INFO, A_PAY_QR) = range(8)

# --- Auto Backup ---
async def send_daily_backup(context: ContextTypes.DEFAULT_TYPE):
    try:
        for file in ['products.json', 'settings.json']:
            if os.path.exists(file):
                await context.bot.send_document(chat_id=config.MY_USER_ID, document=open(file, 'rb'))
    except: pass

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

# --- User Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = SETTINGS['welcome_text']
    img = SETTINGS['welcome_img'] or config.IMG_WELCOME
    if img and os.path.exists(img):
        try:
            await update.message.reply_photo(photo=open(img, 'rb'), caption=welcome_text, reply_markup=await main_menu(), parse_mode='HTML')
            return
        except: pass
    await update.message.reply_text(welcome_text, reply_markup=await main_menu(), parse_mode='HTML')

# --- Callback Handler (Fixed Photo Logic) ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # Category & Product Logic
    if data in SETTINGS['categories'] or data.startswith('cat_'):
        keyboard = [[InlineKeyboardButton(f"{p['name']} - {p['price']}", callback_data=f"v_{p_id}")] for p_id, p in PRODUCTS.items() if p['category'] == data]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_caption(caption="📦 <b>ပစ္စည်းရွေးချယ်ပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('v_'):
        p_id = data.replace('v_', '')
        p = PRODUCTS.get(p_id)
        if p:
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
                # Short Keys for Reliability
                btn_id = f"b_{pay_id[-4:]}_{p_id[-4:]}"
                keyboard.append([InlineKeyboardButton(pay['name'], callback_data=btn_id)])
                context.bot_data[f"pay_{pay_id[-4:]}"] = pay_id
                context.bot_data[f"prod_{p_id[-4:]}"] = p_id
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"v_{p_id}")])
        await query.edit_message_caption(caption="💳 <b>ငွေလွှဲမည့် အကောင့်ရွေးပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # THE CRITICAL FIX: Sending QR Photo
    elif data.startswith('b_'):
        parts = data.split('_')
        pay_id = context.bot_data.get(f"pay_{parts[1]}")
        p_id = context.bot_data.get(f"prod_{parts[2]}")
        
        pay = SETTINGS['payments'].get(pay_id)
        p = PRODUCTS.get(p_id)
        
        if pay and p:
            caption = f"✅ <b>ဝယ်ယူမည့်:</b> {p['name']}\n💰 <b>ကျသင့်ငွေ:</b> {p['price']}\n\n{pay['info']}\n\n⚠️ Screenshot ပို့ပေးပါ။"
            try:
                # Attempt to send photo
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=pay['qr'], caption=caption, parse_mode='HTML')
                await query.message.delete()
            except Exception as e:
                # If photo fails, send as text
                await context.bot.send_message(chat_id=query.message.chat_id, text=f"{caption}\n\n<i>(QR Code ပုံ ပို့ရန် အခက်အခဲရှိနေသဖြင့် Admin ကို တိုက်ရိုက်မေးမြန်းပါ)</i>", parse_mode='HTML')
                logging.error(f"Failed to send QR: {e}")

    # Admin Logic
    elif data == 'adm_manage_pay':
        keyboard = [[InlineKeyboardButton("➕ အကောင့်သစ်ထည့်", callback_data='adm_add_pay_start')]]
        for pid, pay in SETTINGS['payments'].items():
            keyboard.append([InlineKeyboardButton(f"🗑 {pay['name']}", callback_data=f"dp_{pid}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("💳 <b>Payment စီမံရန်</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('dp_'):
        pid = data.replace('dp_', '')
        if pid in SETTINGS['payments']: del SETTINGS['payments'][pid]
        db.save('settings.json', SETTINGS)
        await query.edit_message_text("✅ ဖျက်ပြီးပါပြီ။", reply_markup=admin_home_menu())

    elif data == 'adm_manage_p':
        keyboard = [[InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"dlp_{pid}")] for pid, p in PRODUCTS.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("📦 <b>ပစ္စည်းစာရင်း</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('dlp_'):
        pid = data.replace('dlp_', '')
        if pid in PRODUCTS: del PRODUCTS[pid]
        db.save('products.json', PRODUCTS)
        await query.edit_message_text("✅ ဖျက်ပြီးပါပြီ။", reply_markup=admin_home_menu())

    elif data == 'adm_back_home':
        await query.edit_message_text("🛠 <b>Admin Panel</b>", reply_markup=admin_home_menu(), parse_mode='HTML')

    elif data == 'back_main':
        await query.edit_message_caption(caption=SETTINGS['welcome_text'], reply_markup=await main_menu(), parse_mode='HTML')

# --- Admin Conversations (Fixed Photo Collection) ---
async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("💳 <b>Payment နာမည်</b> (Kpay/Wave)")
    return A_PAY_NAME

async def add_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pn'] = update.message.text
    await update.message.reply_text("📞 <b>အချက်အလက် (နံပါတ်/နာမည်)</b>")
    return A_PAY_INFO

async def add_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pi'] = update.message.text
    await update.message.reply_text("📸 <b>QR Code ပုံ ပို့ပေးပါ</b>")
    return A_PAY_QR

async def add_pay_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ ပုံတစ်ပုံ ပို့ပေးပါ။")
        return A_PAY_QR
    
    pay_id = f"pay_{int(datetime.now().timestamp())}"
    # Grab the best quality photo ID
    photo_id = update.message.photo[-1].file_id
    
    SETTINGS['payments'][pay_id] = {
        "name": context.user_data['pn'],
        "info": context.user_data['pi'],
        "qr": photo_id
    }
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ Payment ထည့်ပြီးပါပြီ။", reply_markup=admin_home_menu())
    return ConversationHandler.END

# ... Product & Welcome functions (Keep them as they are) ...
async def add_p_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✨ <b>ပစ္စည်းအမည် ရိုက်ပို့ပါ</b>")
    return A_P_NAME

async def add_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['n'] = update.message.text
    await update.message.reply_text("💰 <b>စျေးနှုန်း</b>")
    return A_P_PRICE

async def add_p_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pr'] = update.message.text
    await update.message.reply_text("📖 <b>Detail</b>")
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

async def run_bot():
    app = Application.builder().token(config.TOKEN).build()
    
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
            A_P_CAT: [CallbackQueryHandler(add_p_final, pattern="^cat_menu_|^c[1-4]$")],
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
