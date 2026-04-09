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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
import logging

# Logger
logging.basicConfig(level=logging.INFO)

# Env variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "8353264846:AAHlGhCK7z7iNG8cwOCt6Sff6gDEcr3VSvM")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROUP_ID = os.getenv("GROUP_ID", "-1003926587727")
TOPIC_ASOSIY = os.getenv("TOPIC_ASOSIY", "")

# Initialize Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Bot & Dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# FastAPI App
app = FastAPI()

# States
class OrderForm(StatesGroup):
    name = State()
    phone = State()
    location = State()
    items = State()

class MediaUpload(StatesGroup):
    waiting_for_media = State()

# ----------------- /start -----------------
@router.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer("Assalomu alaykum, Maryam Mebel botiga xush kelibsiz!\nBuyurtma berish uchun /new_order buyrug'ini bosing.")

# ----------------- /new_order (FSM) -----------------
@router.message(Command("new_order"))
async def new_order_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Sizning ismingiz nima?")
    await state.set_state(OrderForm.name)

@router.message(OrderForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Telefon raqamingizni kiriting:")
    await state.set_state(OrderForm.phone)

@router.message(OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("Manzilingizni kiriting (yoki lokatsiya yuboring):")
    await state.set_state(OrderForm.location)

@router.message(OrderForm.location)
async def process_location(message: types.Message, state: FSMContext):
    loc_text = message.text if message.text else "Lokatsiya yuborildi"
    await state.update_data(location=loc_text)
    
    # Initialize items
    items = {"Shkaf": 0, "Oshxona": 0, "Stol": 0}
    await state.update_data(items=items)
    
    kb = generate_items_keyboard(items)
    await message.answer("Mahsulotlarni belgilang:", reply_markup=kb)
    await state.set_state(OrderForm.items)

def generate_items_keyboard(items: dict):
    buttons = []
    for k, v in items.items():
        buttons.append([
            InlineKeyboardButton(text=f"➖", callback_data=f"item_sub_{k}"),
            InlineKeyboardButton(text=f"{k}: {v} ta", callback_data="ignore"),
            InlineKeyboardButton(text=f"➕", callback_data=f"item_add_{k}")
        ])
    buttons.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="items_done")])
    buttons.append([InlineKeyboardButton(text="📝 Edit (Boshidan boshlash)", callback_data="edit_order")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(OrderForm.items, F.data.startswith("item_"))
async def process_items_callback(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    item_name = callback.data.split("_")[2]
    
    data = await state.get_data()
    items = data.get("items", {"Shkaf": 0, "Oshxona": 0, "Stol": 0})
    
    if action == "add":
        items[item_name] += 1
    elif action == "sub" and items[item_name] > 0:
        items[item_name] -= 1
        
    await state.update_data(items=items)
    await callback.message.edit_reply_markup(reply_markup=generate_items_keyboard(items))
    await callback.answer()

@router.callback_query(F.data == "edit_order")
async def edit_order_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Ma'lumotlarni bekor qildik. Ismingizni qaytadan kiriting:")
    await state.set_state(OrderForm.name)
    await callback.answer()

@router.callback_query(F.data == "items_done")
async def items_done_callback(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    phone = data.get('phone')
    location = data.get('location')
    items = data.get('items', {})
    
    # Save to Supabase
    order_id = "LOCAL_TEST"
    if supabase:
        try:
            res = supabase.table("orders").insert({
                "customer_name": name,
                "phone": phone,
                "location": location,
                "items": items,
                "status": "NEW"
            }).execute()
            if res.data:
                order_id = res.data[0]['id']
        except Exception as e:
            logging.error(f"Supabase Error: {e}")
            
    # Send to group
    items_text = ", ".join([f"{k}: {v}" for k, v in items.items() if v > 0])
    msg_text = f"🆕 <b>YANGI BUYURTMA</b>\n\n🆔 ID: <code>{order_id}</code>\n👤 Ism: {name}\n📞 Tel: {phone}\n📍 Manzil: {location}\n📦 Mahsulotlar: {items_text}"
    
    status_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Status -> MEASUREMENT 📏", callback_data=f"status_MEASUREMENT_{order_id}")],
        [InlineKeyboardButton(text="Status -> PRODUCTION 🪚", callback_data=f"status_PRODUCTION_{order_id}")],
        [InlineKeyboardButton(text="Status -> DONE ✅", callback_data=f"status_DONE_{order_id}")]
    ])
    
    thread_id = int(TOPIC_ASOSIY) if TOPIC_ASOSIY else None
    
    try:
        await bot.send_message(chat_id=GROUP_ID, message_thread_id=thread_id, text=msg_text, reply_markup=status_kb)
    except Exception as e:
        logging.error(f"Telegram Send Error: {e}")
        # fallback without topic if it fails
        await bot.send_message(chat_id=GROUP_ID, text=msg_text, reply_markup=status_kb)
        
    await callback.message.answer(f"Buyurtma qabul qilindi! Buyurtma ID: {order_id}")
    await state.clear()
    await callback.answer()

# ----------------- Status Updates -----------------
@router.callback_query(F.data.startswith("status_"))
async def status_update_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    new_status = parts[1]
    order_id = parts[2]
    
    if supabase:
        supabase.table("orders").update({"status": new_status}).eq("id", order_id).execute()
        
    await callback.message.answer(f"✅ Order {order_id} statusi {new_status} ga o'zgardi!")
    
    thread_id = int(TOPIC_ASOSIY) if TOPIC_ASOSIY else None
    await bot.send_message(chat_id=GROUP_ID, message_thread_id=thread_id, text=f"🔄 <b>STATUS YANGILANDI</b>\n\n🆔 Buyurtma: <code>{order_id}</code>\n📊 Yangi holat: {new_status}")
    await callback.answer()

# ----------------- /order -----------------
@router.message(Command("order"))
async def order_list_cmd(message: types.Message):
    if not supabase:
        await message.answer("Baza ulanmagan.")
        return
        
    res = supabase.table("orders").select("id, customer_name, status").neq("status", "DONE").execute()
    orders = res.data
    
    if not orders:
        await message.answer("Faol buyurtmalar yo'q.")
        return
        
    kb_list = []
    for o in orders:
        kb_list.append([InlineKeyboardButton(text=f"{o['customer_name']} [{o['status']}]", callback_data=f"select_order_{o['id']}")])
        
    await message.answer("Buyurtmani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@router.callback_query(F.data.startswith("select_order_"))
async def select_order_callback(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.split("select_order_")[1]
    await state.update_data(selected_order_id=order_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Xona (Rasm)", callback_data="upload_xona"),
            InlineKeyboardButton(text="Zamer", callback_data="upload_zamer")
        ],
        [
            InlineKeyboardButton(text="Dizayn", callback_data="upload_dizayn"),
            InlineKeyboardButton(text="Smeta", callback_data="upload_smeta")
        ]
    ])
    
    await callback.message.edit_text(f"Tanlangan Buyurtma: {order_id}\n\nQaysi turni yuklamoqchisiz?", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("upload_"))
async def upload_type_callback(callback: CallbackQuery, state: FSMContext):
    media_type = callback.data.split("upload_")[1]
    await state.update_data(upload_type=media_type)
    await state.set_state(MediaUpload.waiting_for_media)
    await callback.message.answer(f"Iltimos, {media_type} rasm yoki faylini yuboring.")
    await callback.answer()

@router.message(MediaUpload.waiting_for_media, F.photo | F.document)
async def handle_media_upload(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("selected_order_id")
    media_type = data.get("upload_type")
    
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = message.document.file_id
        
    if supabase and order_id:
        supabase.table("order_media").insert({
            "order_id": order_id,
            "media_type": media_type,
            "file_id": file_id
        }).execute()
        
        await message.answer(f"✅ {media_type} bazaga saqlandi!")
        
        # notify group
        thread_id = int(TOPIC_ASOSIY) if TOPIC_ASOSIY else None
        
        caption = f"📎 <b>Yangi fayl yuklandi:</b> {media_type.upper()}\n🆔 Order ID: <code>{order_id}</code>"
        try:
            if message.photo:
                await bot.send_photo(chat_id=GROUP_ID, photo=file_id, caption=caption, message_thread_id=thread_id)
            else:
                await bot.send_document(chat_id=GROUP_ID, document=file_id, caption=caption, message_thread_id=thread_id)
        except Exception as e:
            await message.answer("Fayl guruhga yuborilmadi (xatolik) lekin bazaga tushdi.")
            
    await state.clear()

dp.include_router(router)

@app.post("/api/webhook") # or just the path you configure in vercel webhook url
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
