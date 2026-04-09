import os
import json
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from supabase import create_client, Client
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto, InputMediaDocument
from aiogram.client.default import DefaultBotProperties
import logging
import asyncio

# Logger
logging.basicConfig(level=logging.INFO)

# Env variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8353264846:AAHlGhCK7z7iNG8cwOCt6Sff6gDEcr3VSvM")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROUP_ID = os.getenv("GROUP_ID", "-1003926147374")
TOPIC_ORDER = os.getenv("TOPIC_ORDER", os.getenv("TOPIC_ASOSIY", ""))
TOPIC_XONA = os.getenv("TOPIC_XONA", "")
TOPIC_ZAMER = os.getenv("TOPIC_ZAMER", "")
TOPIC_DIZAYN = os.getenv("TOPIC_DIZAYN", "")
TOPIC_PRODUCTION = os.getenv("TOPIC_ISHLAB_CHIQARISH", "")
TOPIC_DONE = os.getenv("TOPIC_DONE", "")

# Initialize Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Bot & Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

app = FastAPI()

class OrderForm(StatesGroup):
    name = State()
    phone = State()
    location = State()
    categories = State()
    xona_photos = State()
    measurements = State()
    design_photos = State()
    deadline = State()
    password = State()

def skip_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⏭ O'tkazib yuborish"), KeyboardButton(text="➡️ Davom etish")]], resize_keyboard=True)

def next_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➡️ Davom etish")]], resize_keyboard=True)

@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Assalomu alaykum, Maryam Mebel botiga xush kelibsiz!\nBuyurtma berish uchun /new_order buyrug'ini bosing.", reply_markup=ReplyKeyboardRemove())

@router.message(Command("new_order"))
async def new_order_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(
        categories=[], xona=[], zamer=[], dizayn=[]
    )
    await message.answer("Ismingiz nima (FISH)?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.name)

@router.message(OrderForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Telefon raqamingizni kiriting:")
    await state.set_state(OrderForm.phone)

@router.message(OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("O'rnatish manzilini kiriting (yoki lokatsiya yuboring):")
    await state.set_state(OrderForm.location)

@router.message(OrderForm.location)
async def process_location(message: types.Message, state: FSMContext):
    loc_text = message.text if message.text else "Lokatsiya yuborildi"
    await state.update_data(location=loc_text)
    
    cat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Shkaf", callback_data="cat_Shkaf"), InlineKeyboardButton(text="Krovat", callback_data="cat_Krovat")],
        [InlineKeyboardButton(text="Parta", callback_data="cat_Parta"), InlineKeyboardButton(text="Komod", callback_data="cat_Komod")],
        [InlineKeyboardButton(text="✅ Davom etish", callback_data="cat_done")]
    ])
    await message.answer("Kategoriyalarni tanlang:", reply_markup=cat_kb)
    await state.set_state(OrderForm.categories)

@router.callback_query(OrderForm.categories, F.data.startswith("cat_"))
async def process_cats(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")[1]
    
    sdata = await state.get_data()
    cats = sdata.get("categories", [])
    
    if data == "done":
        if not cats:
            await callback.answer("Eng kamida 1 ta kategoriya tanlang!", show_alert=True)
            return
        await callback.message.delete()
        await callback.message.answer(f"Tanlandi: {', '.join(cats)}\n\nEndi Xona rasmlarini yuboring (yoki O'tkazib yuborishni bosing).", reply_markup=skip_kb())
        await state.set_state(OrderForm.xona_photos)
        return
        
    if data in cats: cats.remove(data)
    else: cats.append(data)
    
    await state.update_data(categories=cats)
    
    cat_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Shkaf {'✅' if 'Shkaf' in cats else ''}", callback_data="cat_Shkaf"), 
         InlineKeyboardButton(text=f"Krovat {'✅' if 'Krovat' in cats else ''}", callback_data="cat_Krovat")],
        [InlineKeyboardButton(text=f"Parta {'✅' if 'Parta' in cats else ''}", callback_data="cat_Parta"), 
         InlineKeyboardButton(text=f"Komod {'✅' if 'Komod' in cats else ''}", callback_data="cat_Komod")],
        [InlineKeyboardButton(text="✅ Davom etish", callback_data="cat_done")]
    ])
    try:
        await callback.message.edit_reply_markup(reply_markup=cat_kb)
    except: pass
    await callback.answer()

@router.message(OrderForm.xona_photos)
async def process_xona(message: types.Message, state: FSMContext):
    if message.text in ["⏭ O'tkazib yuborish", "➡️ Davom etish"]:
        await message.answer("O'lchamlar (Zamer) rasmini yoki ma'lumotlarini yuboring. Bu bosqichni o'tkazib yuborib bo'lmaydi!", reply_markup=next_kb())
        await state.set_state(OrderForm.measurements)
        return
    
    if message.photo:
        sdata = await state.get_data()
        xona = sdata.get("xona", [])
        xona.append(message.photo[-1].file_id)
        await state.update_data(xona=xona)

@router.message(OrderForm.measurements)
async def process_measurements(message: types.Message, state: FSMContext):
    sdata = await state.get_data()
    
    if message.text == "➡️ Davom etish":
        if not sdata.get("zamer") and not sdata.get("zamer_text"):
            await message.answer("Iltimos, o'lchamlarni kiriting yoki rasm yuklang!")
            return
        await message.answer("Dizayn namunalarini yuboring (yoki O'tkazib yuborish):", reply_markup=skip_kb())
        await state.set_state(OrderForm.design_photos)
        return
        
    if message.photo:
        zamer = sdata.get("zamer", [])
        zamer.append(message.photo[-1].file_id)
        await state.update_data(zamer=zamer)
    elif message.text:
        zamer_text = sdata.get("zamer_text", "") + "\n" + message.text
        await state.update_data(zamer_text=zamer_text)

@router.message(OrderForm.design_photos)
async def process_design(message: types.Message, state: FSMContext):
    if message.text in ["⏭ O'tkazib yuborish", "➡️ Davom etish"]:
        await message.answer("Qat'iy muddatni kiriting (yoki O'tkazib yuborish):", reply_markup=skip_kb())
        await state.set_state(OrderForm.deadline)
        return
        
    if message.photo:
        sdata = await state.get_data()
        dizayn = sdata.get("dizayn", [])
        dizayn.append(message.photo[-1].file_id)
        await state.update_data(dizayn=dizayn)

@router.message(OrderForm.deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    deadline = message.text
    if message.text in ["⏭ O'tkazib yuborish", "➡️ Davom etish"]:
        deadline = "Neizvestno"
    
    await state.update_data(deadline=deadline)
    await message.answer("Tasdiqlash uchun Maxsus Parolingizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.password)

@router.message(OrderForm.password)
async def process_password(message: types.Message, state: FSMContext):
    pwd = message.text
    
    # Authenticate
    if not supabase:
        await message.answer("Baza ulanmagan.")
        return
        
    res = supabase.table("employees").select("*").eq("password", pwd).execute()
    if not res.data:
        await message.answer("Noto'g'ri parol! Qaytadan kiriting:")
        return
        
    employee = res.data[0]
    
    # Save order
    sdata = await state.get_data()
    
    try:
        ins = supabase.table("orders").insert({
            "customer_name": sdata['name'],
            "phone": sdata['phone'],
            "location": sdata['location'],
            "categories": sdata['categories'],
            "measurements": sdata.get('zamer_text', "Rasm orqali berilgan"),
            "deadline": sdata['deadline'],
            "employee_id": employee['id'],
            "status": "Savatda"
        }).execute()
        
        order_id = ins.data[0]['id']
        
        # Save media logically inside Supabase
        for group, items in [('xona', sdata['xona']), ('zamer', sdata['zamer']), ('dizayn', sdata['dizayn'])]:
            for fid in items:
                supabase.table("order_media").insert({"order_id": order_id, "media_type": group, "file_id": fid}).execute()
                
    except Exception as e:
        await message.answer(f"Xatolik saqlashda: {e}")
        return
        
    # Send texts to topics
    cat_text = ", ".join(sdata['categories'])
    msg_text = f"🆕 <b>YANGI BUYURTMA</b>\n\n🆔 ID: <code>{order_id}</code>\n👤 Mijoz: {sdata['name']}\n📞 Tel: {sdata['phone']}\n📍 Manzil: {sdata['location']}\n📦 Kategoriyalar: {cat_text}\n📏 O'lcham: {sdata.get('zamer_text', 'Faqat rasm')}\n⏳ Muddat: {sdata['deadline']}\n\n👷‍♂️ <b>Qabul qildi:</b> {employee['name']} ({employee['phone']})"
    
    status_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Texnologda", callback_data=f"st_Texnologda_{order_id}"), InlineKeyboardButton(text="Ishlab chiqarishda", callback_data=f"st_Ishlab chiqarishda_{order_id}")],
        [InlineKeyboardButton(text="Yetkazishda", callback_data=f"st_Yetkazishda_{order_id}"), InlineKeyboardButton(text="O'rnatishda", callback_data=f"st_O'rnatishda_{order_id}")],
        [InlineKeyboardButton(text="Topshirilgan ✅", callback_data=f"st_Topshirilgan_{order_id}")],
        [InlineKeyboardButton(text="🛑 Xatolik sabab toxtab qolgan", callback_data=f"st_Xatolik_{order_id}")]
    ])
    
    t_order = int(TOPIC_ORDER) if TOPIC_ORDER else None
    
    try:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=t_order, text=msg_text, reply_markup=status_kb)
    except:
        await bot.send_message(chat_id=GROUP_ID, text=msg_text, reply_markup=status_kb)
        
    # Send Media Groups
    async def send_group_to_topic(topic_str, group_type, title, items):
        if not items: return
        tid = int(topic_str) if topic_str else t_order
        media = []
        for i, fid in enumerate(items):
            if i == 0:
                media.append(InputMediaPhoto(media=fid, caption=f"📁 {title}\n🆔 {order_id}\n👤 Mijoz: {sdata['name']}\n👷‍♂️ Qabul qildi: {employee['name']}"))
            else:
                media.append(InputMediaPhoto(media=fid))
        try:
            await bot.send_media_group(chat_id=GROUP_ID, media=media, message_thread_id=tid)
        except Exception as e:
            logging.error(f"MediaGroup error {group_type}: {e}")

    await send_group_to_topic(TOPIC_XONA, "xona", "XONA RASMLARI", sdata['xona'])
    await send_group_to_topic(TOPIC_ZAMER, "zamer", "O'LCHAMLAR (ZAMER)", sdata['zamer'])
    await send_group_to_topic(TOPIC_DIZAYN, "dizayn", "DIZAYN NAMUNALARI", sdata['dizayn'])
    
    await message.answer(f"✅ Barchasi qabul qilindi. Buyurtma ID: {order_id}")
    await state.clear()

@router.callback_query(F.data.startswith("st_"))
async def update_status_cb(callback: CallbackQuery):
    parts = callback.data.split("_")
    new_status = parts[1]
    order_id = parts[2]
    
    if new_status == "Xatolik":
        new_status = "Xatolik sabab toxtab qolgan"
        
    if supabase:
        supabase.table("orders").update({"status": new_status}).eq("id", order_id).execute()
        
    await callback.message.reply(f"🔄 Buyurtma statusi: <b>{new_status}</b>", parse_mode="HTML")
    await callback.answer(f"Status: {new_status}")

@router.message(Command("buyurtmalar"))
async def list_orders(message: types.Message):
    if not supabase: return
    res = supabase.table("orders").select("id, customer_name, status, deadline").neq("status", "Topshirilgan").execute()
    if not res.data:
        await message.answer("Faol buyurtmalar yo'q.")
        return
    text = "📋 <b>Faol Buyurtmalar:</b>\n\n"
    for o in res.data:
        text += f"🆔 <code>/order_{o['id'].replace('-','')}</code>\n👤 {o['customer_name']} - <b>{o['status']}</b> (Muddat: {o['deadline']})\n\n"
    await message.answer(text)

@router.message(F.text.startswith("/order_"))
async def view_order(message: types.Message):
    if not supabase: return
    short_id = message.text.replace("/order_", "")
    # Short ID matched with UUID logic is a bit tricky, let's just do a search
    # This is a bit inefficient if lots of orders but works
    res = supabase.table("orders").select("*, employees(name, phone)").execute()
    
    order = None
    for o in res.data:
        if o['id'].replace('-', '') == short_id:
            order = o
            break
            
    if not order:
        await message.answer("Buyurtma topilmadi.")
        return
        
    emp = order.get('employees', {})
    emp_name = emp.get('name', 'Noma''lum')
    
    cat_text = ", ".join(order['categories'])
    msg_text = f"📄 <b>BUYURTMA MA'LUMOTI</b>\n\n🆔 <code>{order['id']}</code>\n👤 Mijoz: {order['customer_name']}\n📞 Tel: {order['phone']}\n📍 Manzil: {order['location']}\n📦 Kategoriyalar: {cat_text}\n📏 O'lcham: {order['measurements']}\n⏳ Muddat: {order.get('deadline','Neizvestno')}\n📅 Olingan sana: {order['created_at'][:10]}\n\n👷‍♂️ <b>Xodim:</b> {emp_name}\n\n📊 <b>STATUS: {order['status']}</b>"
    
    status_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Texnologda", callback_data=f"st_Texnologda_{order['id']}"), InlineKeyboardButton(text="Ishlab chiqarishda", callback_data=f"st_Ishlab chiqarishda_{order['id']}")],
        [InlineKeyboardButton(text="Yetkazishda", callback_data=f"st_Yetkazishda_{order['id']}"), InlineKeyboardButton(text="O'rnatishda", callback_data=f"st_O'rnatishda_{order['id']}")],
        [InlineKeyboardButton(text="Topshirilgan ✅", callback_data=f"st_Topshirilgan_{order['id']}")],
        [InlineKeyboardButton(text="🛑 Xatolik", callback_data=f"st_Xatolik_{order['id']}")]
    ])
    
    await message.answer(msg_text, reply_markup=status_kb)

dp.include_router(router)

@app.post("/api/webhook")
async def webhook(request: Request):
    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        await dp.feed_update(bot=bot, update=telegram_update)
    except Exception as e:
        logging.error(f"Error handling webhook: {e}")
    return {"status": "ok"}

@app.get("/api/ping")
async def ping():
    return {"status": "alive"}
