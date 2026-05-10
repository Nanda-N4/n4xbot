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
from telegram.constants import ChatAction

import config
from db_manager import DBManager

# --- Init & Logging ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(message)s', level=logging.INFO)
db = DBManager()

# Load Data
PRODUCTS = db.load('products.json', {})
SETTINGS = db.load('settings.json', {
    "welcome_text": "👋 မင်္ဂလာပါ [user_name]။\n✨ <b>Nanda VPN Services</b> မှ ကြိုဆိုပါတယ်။ ✨\n\n🤖 ကျွန်တော်ကတော့ ကိုနန္ဒရဲ့ <b>Auto-Reply AI Bot</b> ဖြစ်ပါတယ်။\nလိုအပ်တာလေးတွေကို အောက်ပါ Menu ကိုနှိပ်ပြီး ရွေးချယ် ကြည့်ရှုနိုင်ပါသည်ခင်ဗျာ။ 👇",
    "payments": {},
    "categories": {} 
})

# States for Conversations
(A_P_NAME, A_P_PRICE, A_P_DESC, A_P_CAT, E_WELCOME, 
 A_PAY_TYPE, A_PAY_INFO, A_CAT_NAME, A_CAT_PROTO) = range(9)

# --- Constants from Old Code (Converted to HTML) ---
BUYING_GUIDE = (
    "📖 <b>ဝယ်ယူနည်း အဆင့်ဆင့် လမ်းညွှန်</b>\n\n"
    "1️⃣ <b>Product ရွေးချယ်ပါ</b> - Menu ထဲမှ မိမိဝယ်ယူလိုသော ဝန်ဆောင်မှုကို နှိပ်ပါ။\n"
    "2️⃣ <b>Type ရွေးချယ်ပါ</b> - V2ray သို့မဟုတ် Outline ကို ရွေးချယ်ပါ။\n"
    "3️⃣ <b>အတည်ပြုပါ</b> - စျေးနှုန်းကို စစ်ဆေးပြီး '🛒 ဝယ်ယူမည်' ကို နှိပ်ပါ။\n"
    "4️⃣ <b>ငွေလွှဲပါ</b> - ကျလာသော ဖုန်းနံပတ်သို့ သတ်မှတ်စျေးနှုန်းအတိုင်း လွှဲပေးပါ။\n"
    "5️⃣ <b>ပြေစာပို့ပါ</b> - ငွေလွှဲပြီးကြောင်း Screenshot ကို ဤ Chat ထဲသို့ ပို့ပေးပါ။\n"
    "6️⃣ <b>စောင့်ဆိုင်းပါ</b> - Admin မှ ပြေစာကို စစ်ဆေးပြီး မိနစ်ပိုင်းအတွင်း Product ပို့ပေးပါမည်。\n\n"
    "🤖 <i>ကျွန်တော်သည် အလိုအလျောက် စာပြန်ပေးသော AI ဖြစ်သဖြင့် ငွေလွှဲပြေစာ စစ်ဆေးခြင်းကိုတော့ Admin ကိုယ်တိုင် ဆောင်ရွက်ပေးရခြင်း ဖြစ်ပါသည်။</i>"
)

ATOM_MSG = (
    "📢 <b>Atom လိုင်းဖြတ် VIP အသုံးပြုသူများအတွက် အသိပေးချက်</b>\n\n"
    "⚠️ လက်ရှိတွင် အော်ပရေတာဘက်မှ ပိတ်လိုက်သောကြောင့် အသုံးပြု၍ မရသေးပါခင်ဗျာ။ "
    "ပြန်လည်အသုံးပြုနိုင်ရန် နည်းသစ်များ ရှာဖွေ ကြိုးစားနေပါသည်။\n\n"
    "🔄 <b>ပြန်လည်ရရှိသည်နှင့် တပြိုင်နက်</b> ယခင်ဝယ်ယူထားသော Customer များအားလုံးကို "
    "<b>တစ်ကြိမ် အလကား (Free)</b> ပြန်လည်လဲလှယ်ပေးသွားပါမည်။\n\n"
    "🤝 စောင့်ဆိုင်းပေးနေကြသော တစ်ဦးတစ်ယောက်ချင်းစီကို ကျေးဇူးအထူးတင်ရှိပါသည်ခင်ဗျာ။ 🙏"
)

PAYMENT_WARNING = (
    "⚠️ <b>အရေးကြီးသတိပေးချက်</b>\n"
    "ငွေလွှဲသည့် Note တွင် VPN / Key စသည့် စာသားများ <b>လုံးဝ (လုံးဝ) မရေးပါနဲ့ခင်ဗျာ။</b>\n"
    "<i>(Payment / Bill / Gift စသည့် စာသားများသာ ရေးပေးပါ)</i> ✅\n\n"
    "📸 ငွေလွှဲပြီးပါက ပြေစာ (Screenshot) ပို့ပေးပါဗျ။"
)

# --- Helper Functions ---
def get_cat_name(cid):
    cat = SETTINGS['categories'].get(cid, "ပစ္စည်းများ")
    return cat['name'] if isinstance(cat, dict) else str(cat)

def is_proto_enabled(cid):
    cat = SETTINGS['categories'].get(cid)
    return cat.get('has_protocol', False) if isinstance(cat, dict) else False

async def send_typing(context, chat_id):
    try: await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING); await asyncio.sleep(0.5)
    except: pass

async def main_menu_markup():
    keyboard = [[InlineKeyboardButton(get_cat_name(cid), callback_data=f"cat_{cid}")] for cid in SETTINGS['categories']]
    keyboard.append([InlineKeyboardButton("📖 ဝယ်ယူနည်း လမ်းညွှန်", callback_data='how_to_buy')])
    keyboard.append([InlineKeyboardButton("👨‍💻 Admin နှင့် တိုက်ရိုက်ပြောရန်", url=config.ADMIN_LINK)])
    return InlineKeyboardMarkup(keyboard)

async def admin_home_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Products စီမံရန်", callback_data='adm_manage_p')],
        [InlineKeyboardButton("➕ ပစ္စည်းအသစ်ထည့်ရန်", callback_data='adm_add_start')],
        [InlineKeyboardButton("📂 Categories စီမံရန်", callback_data='adm_manage_cat')],
        [InlineKeyboardButton("💳 Payments စီမံရန်", callback_data='adm_manage_pay')],
        [InlineKeyboardButton("👋 Welcome စာပြင်ရန်", callback_data='adm_edit_welcome')],
        [InlineKeyboardButton("❌ Exit Panel", callback_data='adm_close')]
    ])

# --- User Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_typing(context, update.effective_chat.id)
    user_name = update.effective_user.first_name if update.effective_user else "မိတ်ဆွေ"
    welcome_text = SETTINGS['welcome_text'].replace("[user_name]", user_name)
    img = config.IMG_WELCOME
    markup = await main_menu_markup()
    if os.path.exists(img):
        await update.message.reply_photo(photo=open(img, 'rb'), caption=welcome_text, reply_markup=markup, parse_mode='HTML')
    else:
        await update.message.reply_text(welcome_text, reply_markup=markup, parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not update.effective_user or update.effective_user.id == config.MY_USER_ID: return

    await send_typing(context, update.effective_chat.id)

    # Photo Auto Reply
    if msg.photo:
        await msg.reply_text(
            "✅ <b>ပြေစာ/ပုံ ပေးပို့မှု လက်ခံရရှိပါတယ်ခင်ဗျာ။</b>\n\n"
            "👨‍💻 Admin မှ အမြန်ဆုံး စစ်ဆေးပေးပါမည်။ ခဏလေးစောင့်ပေးပါခင်ဗျာ။ 🙏\n\n"
            "🤖 <i>(AI Bot မှ အလိုအလျောက်ပြန်ကြားခြင်းဖြစ်ပါတယ်ခင်ဗျာ။)</i>",
            parse_mode='HTML'
        )
        return

    text = msg.text.lower() if msg.text else ""

    # Keyword Triggers
    if any(k in text for k in ['atom', 'ပိတ်', 'မရတော့', 'မရဘူး', 'မရတော့ပါလား']):
        await msg.reply_text(ATOM_MSG, parse_mode='HTML')
        return
    if any(k in text for k in ['ဝယ်နည်း', 'how to buy', 'ဘယ်လိုဝယ်ရမလဲ']):
        await msg.reply_text(BUYING_GUIDE, reply_markup=await main_menu_markup(), parse_mode='HTML')
        return
    if any(k in text for k in ['hi', 'hello', 'မင်္ဂလာပါ', 'စျေးနှုန်း', 'vpn', 'start', 'ဝယ်မယ်']) or msg.sticker:
        await start(update, context)

# --- Callback Handler ---
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == 'back_main' or data == 'back_to_main':
        user_name = update.effective_user.first_name if update.effective_user else "မိတ်ဆွေ"
        welcome_text = SETTINGS['welcome_text'].replace("[user_name]", user_name)
        await query.edit_message_caption(caption=welcome_text, reply_markup=await main_menu_markup(), parse_mode='HTML')
    
    elif data == 'how_to_buy':
        await query.edit_message_caption(caption=BUYING_GUIDE, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data='back_main')]]), parse_mode='HTML')

    elif data.startswith('cat_'):
        cid = data.replace('cat_', '')
        keyboard = [[InlineKeyboardButton(f"{p['name']} - {p['price']}", callback_data=f"v_{p_id}")] for p_id, p in PRODUCTS.items() if p.get('category') == cid]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_main')])
        await query.edit_message_caption(caption=f"📦 <b>{get_cat_name(cid)}</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('v_'):
        p_id = data.replace('v_', '')
        p = PRODUCTS.get(p_id)
        if p:
            caption = f"📦 <b>{p['name']}</b>\n💰 စျေးနှုန်း: <b>{p['price']}</b>\n\n{p.get('desc', '-')}"
            if is_proto_enabled(p['category']):
                keyboard = [[InlineKeyboardButton("🚀 V2ray (Vless)", callback_data=f"proto_v2ray_{p_id}")], [InlineKeyboardButton("🗝 Outline (Shadowsocks)", callback_data=f"proto_outline_{p_id}")], [InlineKeyboardButton("🔙 Back", callback_data=f"cat_{p['category']}")]]
                await query.edit_message_caption(caption=f"{caption}\n\n👇 <b>Protocol ရွေးချယ်ပါ</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            else:
                keyboard = [[InlineKeyboardButton("🛒 ဝယ်ယူမည်", callback_data=f"ps_{p_id}_none")], [InlineKeyboardButton("🔙 Back", callback_data=f"cat_{p['category']}")] ]
                await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('proto_') or data.startswith('ps_'):
        parts = data.split('_')
        p_id, proto = (parts[2], parts[1]) if data.startswith('proto_') else (parts[1], parts[2])
        keyboard = [[InlineKeyboardButton(pay['name'], callback_data=f"buy_{pid}@{p_id}@{proto}")] for pid, pay in SETTINGS['payments'].items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"v_{p_id}")])
        await query.edit_message_caption(caption=f"💳 <b>ငွေလွှဲမည့် အကောင့်ရွေးပါ</b>\n(Protocol: {proto.upper()})", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith('buy_'):
        try:
            parts = data.replace('buy_', '').split('@')
            pay_id, p_id, proto = parts[0], parts[1], parts[2]
            pay, p = SETTINGS['payments'].get(pay_id), PRODUCTS.get(p_id)
            if pay and p:
                proto_str = f"\n⚙️ Protocol: <b>{proto.upper()}</b>" if proto != "none" else ""
                caption = f"✅ <b>ဝယ်ယူမည့်:</b> {p['name']}{proto_str}\n💰 <b>ကျသင့်ငွေ:</b> {p['price']}\n\n📞 {pay['info']}\n\n{PAYMENT_WARNING}"
                qr_file = f"assets/{pay['type']}.png"
                keyboard = [[InlineKeyboardButton("📩 ငွေလွှဲပြီးပါပြီ (Admin သိစေရန်)", callback_data=f"notif_{p_id}_{proto}")], [InlineKeyboardButton("🔙 Back", callback_data=f"ps_{p_id}_{proto}")]]
                
                if os.path.exists(qr_file): await context.bot.send_photo(chat_id=query.message.chat_id, photo=open(qr_file, 'rb'), caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
                else: await context.bot.send_message(chat_id=query.message.chat_id, text=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
                await query.message.delete()
        except: pass

    elif data.startswith('notif_'):
        parts = data.split('_'); p_id, proto = parts[1], parts[2]; p = PRODUCTS.get(p_id); user = query.from_user
        proto_txt = f" ({proto.upper()})" if proto != "none" else ""
        admin_msg = f"🔔 <b>ငွေလွှဲအကြောင်းကြားစာ</b>\n\n👤 User: {user.full_name} (@{user.username})\n📦 ပစ္စည်း: <b>{p['name'] if p else 'N/A'}{proto_txt}</b>\n💰 စျေးနှုန်း: {p['price'] if p else '-'}"
        await context.bot.send_message(chat_id=config.MY_USER_ID, text=admin_msg, parse_mode='HTML')
        await query.edit_message_caption(caption="✅ Admin ထံ အကြောင်းကြားပြီးပါပြီ။ ခေတ္တစောင့်ဆိုင်းပေးပါ။", parse_mode='HTML')

    # Admin Panel Actions
    elif data == 'adm_manage_cat':
        keyboard = [[InlineKeyboardButton("➕ အမျိုးအစားသစ်", callback_data='adm_add_cat_start')]]
        for cid, _ in SETTINGS['categories'].items(): keyboard.append([InlineKeyboardButton(f"🗑 {get_cat_name(cid)}", callback_data=f"dcat_{cid}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("📂 <b>Categories စီမံရန်</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif data == 'adm_manage_p':
        keyboard = [[InlineKeyboardButton(f"🗑 {p['name']}", callback_data=f"dlp_{pid}")] for pid, p in PRODUCTS.items()]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("📦 <b>ပစ္စည်းစာရင်း</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif data == 'adm_manage_pay':
        keyboard = [[InlineKeyboardButton("➕ အကောင့်သစ်", callback_data='adm_add_pay_start')]]
        for pid, pay in SETTINGS['payments'].items(): keyboard.append([InlineKeyboardButton(f"🗑 {pay['name']}", callback_data=f"dp_{pid}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='adm_back_home')])
        await query.edit_message_text("💳 <b>Payment စီမံရန်</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif data.startswith('dcat_'):
        cid = data.replace('dcat_', ''); del SETTINGS['categories'][cid]; db.save('settings.json', SETTINGS)
        await query.edit_message_text("✅ Deleted!", reply_markup=await admin_home_markup())
    elif data.startswith('dlp_'):
        pid = data.replace('dlp_', ''); del PRODUCTS[pid]; db.save('products.json', PRODUCTS)
        await query.edit_message_text("✅ Deleted!", reply_markup=await admin_home_markup())
    elif data.startswith('dp_'):
        pid = data.replace('dp_', ''); del SETTINGS['payments'][pid]; db.save('settings.json', SETTINGS)
        await query.edit_message_text("✅ Deleted!", reply_markup=await admin_home_markup())
    elif data == 'adm_back_home': await query.edit_message_text("🛠 <b>Admin Panel</b>", reply_markup=await admin_home_markup(), parse_mode='HTML')
    elif data == 'adm_close': await query.message.delete()

# --- Admin Conversations (Fixed Async) ---
async def add_cat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📂 <b>Category အမည် ပို့ပေးပါ:</b>", parse_mode='HTML'); return A_CAT_NAME
async def add_cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_cat_name'] = update.message.text
    await update.message.reply_text("⚙️ <b>Protocol (V2ray/Outline) ရွေးခိုင်းမလား?</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes", callback_data="proto_yes")], [InlineKeyboardButton("❌ No", callback_data="proto_no")]]), parse_mode='HTML'); return A_CAT_PROTO
async def add_cat_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    cid = f"cat{int(datetime.now().timestamp())}"
    SETTINGS['categories'][cid] = {"name": context.user_data['temp_cat_name'], "has_protocol": True if update.callback_query.data == "proto_yes" else False}
    db.save('settings.json', SETTINGS); await update.callback_query.message.reply_text("✅ Category Added!", reply_markup=await admin_home_markup()); return ConversationHandler.END

async def add_p_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("✨ <b>ပစ္စည်းအမည်:</b>", parse_mode='HTML'); return A_P_NAME
async def add_p_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['n'] = update.message.text; await update.message.reply_text("💰 <b>စျေးနှုန်း:</b>", parse_mode='HTML'); return A_P_PRICE
async def add_p_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['pr'] = update.message.text; await update.message.reply_text("📖 <b>Description:</b>", parse_mode='HTML'); return A_P_DESC
async def add_p_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['d'] = update.message.text
    keyboard = [[InlineKeyboardButton(get_cat_name(cid), callback_data=cid)] for cid in SETTINGS['categories']]
    await update.message.reply_text("📂 <b>Category ရွေးပါ:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML'); return A_P_CAT
async def add_p_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(); pid = f"p{int(datetime.now().timestamp())}"
    PRODUCTS[pid] = {"name": context.user_data['n'], "price": context.user_data['pr'], "desc": context.user_data['d'], "category": update.callback_query.data}
    db.save('products.json', PRODUCTS); await update.callback_query.message.reply_text("✅ Added!", reply_markup=await admin_home_markup()); return ConversationHandler.END

async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Kpay", callback_data="st_kpay")], [InlineKeyboardButton("Wave Pay", callback_data="st_wave")], [InlineKeyboardButton("AYA Pay", callback_data="st_aya")]]
    await update.callback_query.message.reply_text("💳 <b>အမျိုးအစား:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML'); return A_PAY_TYPE
async def add_pay_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(); context.user_data['ptype'] = update.callback_query.data.replace("st_", "")
    await update.callback_query.message.reply_text(f"📞 <b>{context.user_data['ptype'].upper()} အချက်အလက် (ဖုန်း/နာမည်) ပို့ပါ:</b>", parse_mode='HTML'); return A_PAY_INFO
async def add_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay_id = f"pay{int(datetime.now().timestamp())}"
    SETTINGS['payments'][pay_id] = {"name": context.user_data['ptype'].upper(), "type": context.user_data['ptype'], "info": update.message.text}
    db.save('settings.json', SETTINGS); await update.message.reply_text("✅ Payment Added!", reply_markup=await admin_home_markup()); return ConversationHandler.END

async def welcome_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("📝 <b>Welcome စာသား အသစ်ပို့ပါ (User နာမည်ခေါ်ရန် [user_name] ဟုထည့်ရေးပါ):</b>", parse_mode='HTML'); return E_WELCOME
async def welcome_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SETTINGS['welcome_text'] = update.message.text; db.save('settings.json', SETTINGS)
    await update.message.reply_text("✅ Saved!", reply_markup=await admin_home_markup()); return ConversationHandler.END

async def end_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# --- Admin Cmd ---
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == config.MY_USER_ID:
        markup = await admin_home_markup()
        await update.message.reply_text("🛠 <b>Admin Panel</b>", reply_markup=markup, parse_mode='HTML')

# --- Run Bot ---
async def run_bot():
    app = Application.builder().token(config.TOKEN).build()
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_p_start, "^adm_add_start$"), CallbackQueryHandler(add_pay_start, "^adm_add_pay_start$"), CallbackQueryHandler(welcome_edit_start, "^adm_edit_welcome$"), CallbackQueryHandler(add_cat_start, "^adm_add_cat_start$")],
        states={
            A_P_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_name)], A_P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_price)], A_P_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_p_desc)], A_P_CAT: [CallbackQueryHandler(add_p_final, "^cat")],
            A_PAY_TYPE: [CallbackQueryHandler(add_pay_type, "^st_")], A_PAY_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pay_info)],
            E_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, welcome_edit_save)],
            A_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cat_name)], A_CAT_PROTO: [CallbackQueryHandler(add_cat_final, "^proto_")]
        },
        fallbacks=[CallbackQueryHandler(end_conv, "^adm_back_home$")]
    )
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("admin", admin_cmd)); app.add_handler(admin_conv)
    app.add_handler(CallbackQueryHandler(handle_callbacks)); app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    async with app:
        await app.initialize(); await app.start(); await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(run_bot())
