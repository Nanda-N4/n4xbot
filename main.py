import logging
import json
import os
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    "categories": {
        "cat_menu_vip": "🚀 VIP PRO", 
        "cat_menu_sg": "🇸🇬 Singapore", 
        "cat_menu_jp": "🇯🇵 Japan", 
        "cat_menu_sl": "📡 Starlink"
    }
})

# States
(A_P_NAME, A_P_PRICE, A_P_DESC, A_P_CAT, E_WELCOME, A_PAY_TYPE, A_PAY_INFO) = range(7)

# --- Keyboards ---
async def main_menu():
    keyboard = []
    for cid, name in SETTINGS['categories'].items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"cat_{cid}")])
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

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = SETTINGS['welcome_text']
    img = SETTINGS['welcome_img'] or config.IMG_WELCOME
    if img and os.path.exists(img):
        await update.message.reply_photo(photo=open(img, 'rb'), caption=welcome_text, reply_markup=await main_menu(), parse_mode='HTML')
    else:
        await update.message.reply_text(welcome_text, reply_markup=await main_menu(), parse_mode='HTML')

async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    # User Side: View Category
    if data.startswith('cat_'):
        cid = data.replace('cat_', '')
        keyboard = []
        # အမျိုးအစားတူတာတွေကို အဟောင်းရော အသစ်ရော ရှာပေးမယ်
        for p_id, p in PRODUCTS.items():
            p_cat = p.get('category', '')
            # ID အတို (c1) ၊ အရှည် (cat_menu_vip) ၊ ဒါမှမဟုတ် နာမည် အကုန်တိုက်စစ်မယ်
            if cid in p_cat or p_cat in cid:
                keyboard.append([InlineKeyboardButton(f"{p['name']} - {p['price']}", callback_data=f"v_{p_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_caption(caption="📦 <b>ပစ္စည်းရွေးချယ်ပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # User Side: View Product
    elif data.startswith('v_'):
        p_id = data.replace('v_', '')
        p = PRODUCTS.get(p_id)
        if p:
            caption = f"📦 <b>{p['name']}</b>\n💰 စျေးနှုန်း: <b>{p['price']}</b>\n\n{p.get('desc', '-')}"
            keyboard = [[InlineKeyboardButton("🛒 ဝယ်မည်", callback_data=f"ps_{p_id}")], [InlineKeyboardButton("🔙 Back", callback_data=f"cat_{p['category']}")] ]
            await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # User Side: Select Payment
    elif data.startswith('ps_'):
        p_id = data.replace('ps_', '')
        keyboard = []
        if not SETTINGS['payments']:
            keyboard.append([InlineKeyboardButton("👨‍💻 Admin ထံ တိုက်ရိုက်မေးပါ", url=config.ADMIN_LINK)])
        else:
            for pay_id, pay in SETTINGS['payments'].items():
                keyboard.append([InlineKeyboardButton(pay['name'], callback_data=f"buy_{pay_id}@{p_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"v_{p_id}")])
        await query.edit_message_caption(caption="💳 <b>ငွေလွှဲမည့် အကောင့်ရွေးပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    # User Side: Final Show QR (LOCAL ASSETS ONLY)
    elif data.startswith('buy_'):
        try:
            parts = data.replace('buy_', '').split('@')
            pay_id, p_id = parts[0], parts[1]
            pay = SETTINGS['payments'].get(pay_id)
            p = PRODUCTS.get(p_id)
            
            if pay and p:
                caption = f"✅ <b>Item:</b> {p['name']}\n💰 <b>Price:</b> {p['price']}\n\n{pay['info']}\n\n⚠️ Screenshot ပို့ပေးပါ။"
                qr_file = f"assets/{pay['type']}.png"
                
                if os.path.exists(qr_file):
                    with open(qr_file, 'rb') as photo:
                        await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, caption=caption, parse_mode='HTML')
                else:
                    await context.bot.send_message(chat_id=query.message.chat_id, text=f"{caption}\n\n(QR ပုံမတွေ့ပါ - Admin ကို မေးမြန်းပါ)", parse_mode='HTML')
                await query.message.delete()
        except Exception as e:
            logging.error(f"Buy error: {e}")

    # Admin Panel: Navigation
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
        await query.edit_message_text("✅ Deleted!", reply_markup=admin_home_menu())

    elif data == 'adm_manage_p':
        keyboard = [[InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"dlp_{pid}")] for pid, p in PRODUCTS.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("📦 <b>ပစ္စည်းစာရင်း</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('dlp_'):
        pid = data.replace('dlp_', '')
        if pid in PRODUCTS: del PRODUCTS[pid]
        db.save('products.json', PRODUCTS)
        await query.edit_message_text("✅ Deleted!", reply_markup=admin_home_menu())

    elif data == 'adm_back_home':
        await query.edit_message_text("🛠 Admin Panel", reply_markup=admin_home_menu())

    elif data == 'back_main':
        await query.edit_message_caption(caption=SETTINGS['welcome_text'], reply_markup=await main_menu(), parse_mode='HTML')

# --- Admin Conversations ---
async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Kpay", callback_data="st_kpay")],
        [InlineKeyboardButton("Wave Pay", callback_data="st_wave")],
        [InlineKeyboardButton("AYA Pay", callback_data="st_aya")]
    ]
    await update.callback_query.message.reply_text("💳 <b>ငွေလွှဲအမျိုးအစား:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    return A_PAY_TYPE

async def add_pay_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ptype = update.callback_query.data.replace("st_", "")
    context.user_data['ptype'] = ptype
    await update.callback_query.message.reply_text(f"📞 <b>{ptype.upper()} အချက်အလက် (နံပါတ်/နာမည်) ပို့ပါ:</b>", parse_mode='HTML')
    return A_PAY_INFO

async def add_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay_id = f"pay{int(datetime.now().timestamp())}"
    SETTINGS['payments'][pay_id] = {"name": context.user_data['ptype'].upper(), "type": context.user_data['ptype'], "info": update.message.text}
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ Added!", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def add_p_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✨ <b>ပစ္စည်းအမည်:</b>")
    return A_P_NAME

async def add_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['n'] = update.message.text
    await update.message.reply_text("💰 <b>စျေးနှုန်း:</b>")
    return A_P_PRICE

async def add_p_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pr'] = update.message.text
    await update.message.reply_text("📖 <b>Description:</b>")
    return A_P_DESC

async def add_p_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['d'] = update.message.text
    keyboard = [[InlineKeyboardButton(name, callback_data=cid)] for cid, name in SETTINGS['categories'].items()]
    await update.message.reply_text("📂 <b>Category ရွေးပါ:</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return A_P_CAT

async def add_p_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = f"p{int(datetime.now().timestamp())}"
    PRODUCTS[pid] = {"name": context.user_data['n'], "price": context.user_data['pr'], "desc": context.user_data['d'], "category": update.callback_query.data}
    db.save('products.json', PRODUCTS)
    await update.callback_query.message.reply_text("✅ Added!", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def welcome_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📝 <b>Welcome စာသား ပို့ပါ</b>")
    return E_WELCOME

async def welcome_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SETTINGS['welcome_text'] = update.message.text
    db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ Saved!", reply_markup=admin_home_menu())
    return ConversationHandler.END

async def run_bot():
    app = Application.builder().token(config.TOKEN).build()
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_p_start, pattern="^adm_add_start$"),
            CallbackQueryHandler(add_pay_start, pattern="^adm_add_pay_start$"),
            CallbackQueryHandler(welcome_edit_start, pattern="^adm_edit_welcome$")
        ],
        states={
            A_P_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_name)],
            A_P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_price)],
            A_P_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_desc)],
            A_P_CAT: [CallbackQueryHandler(add_p_final, pattern="^c[1-4]$|^cat_menu_")],
            A_PAY_TYPE: [CallbackQueryHandler(add_pay_type, pattern="^st_")],
            A_PAY_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pay_info)],
            E_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, welcome_edit_save)]
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
