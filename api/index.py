import os
import json
import datetime
import random
import string
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
from supabase import create_client, Client
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto, InputMediaDocument
from aiogram.client.default import DefaultBotProperties
import logging

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROUP_ID = os.getenv("GROUP_ID", "-1003682129136")

# Topic IDlar — har bir bosqich uchun guruh ichidagi topic
TOPIC_ORDER = os.getenv("TOPIC_ORDER", "2")       # Yangi buyurtmalar
TOPIC_XONA = os.getenv("TOPIC_XONA", "3")         # Xona rasmlari
TOPIC_ZAMER = os.getenv("TOPIC_ZAMER", "4")       # O'lchamlar
TOPIC_DESIGN = os.getenv("TOPIC_DESIGN", "5")     # Dizayn rasmlari
TOPIC_FACTORY = os.getenv("TOPIC_FACTORY", "6")   # Ishlab chiqarish
TOPIC_INVENTARY = os.getenv("TOPIC_INVENTARY", "7")  # Inventar/Taminot
TOPIC_ERRORS = os.getenv("TOPIC_ERRORS", "8")     # Xatoliklar
TOPIC_SOP = os.getenv("TOPIC_SOP", "9")           # SOP — Standart operatsion protseduralar
TOPIC_READY = os.getenv("TOPIC_READY", "10")      # Tayyor / Topshirilgan
TOPIC_LOGISTICA = os.getenv("TOPIC_LOGISTICA", "11")  # Yetkazish / Logistika

# Status → Topic mapping (har bir status o'zgarganda xabar qaysi topicga ketishi)
STATUS_TOPIC_MAP = {
    "Savatda": TOPIC_ORDER,
    "Texnologda": TOPIC_SOP,
    "Taminotchida": TOPIC_INVENTARY,
    "Ishlab chiqarishda": TOPIC_FACTORY,
    "Yetkazishda": TOPIC_LOGISTICA,
    "O'rnatishda": TOPIC_LOGISTICA,
    "Topshirilgan": TOPIC_READY,
    "Xatolik sabab toxtab qolgan": TOPIC_ERRORS,
}

ADMIN_USERS = [6690357035]

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


class SupabaseStorage(BaseStorage):
    """Supabase-backed FSM storage — serverless cold start'dan keyin ham holatni saqlaydi."""

    def _key(self, key: StorageKey):
        return key.chat_id, key.user_id

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        chat_id, user_id = self._key(key)
        state_str = state.state if hasattr(state, 'state') else state
        if supabase:
            supabase.table("fsm_states").upsert({
                "chat_id": chat_id, "user_id": user_id,
                "state": state_str
            }, on_conflict="chat_id,user_id").execute()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        chat_id, user_id = self._key(key)
        if not supabase: return None
        res = supabase.table("fsm_states").select("state").eq("chat_id", chat_id).eq("user_id", user_id).execute()
        if res.data: return res.data[0].get("state")
        return None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        chat_id, user_id = self._key(key)
        if supabase:
            supabase.table("fsm_states").upsert({
                "chat_id": chat_id, "user_id": user_id,
                "data": json.dumps(data, default=str)
            }, on_conflict="chat_id,user_id").execute()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        chat_id, user_id = self._key(key)
        if not supabase: return {}
        res = supabase.table("fsm_states").select("data").eq("chat_id", chat_id).eq("user_id", user_id).execute()
        if res.data:
            raw = res.data[0].get("data", "{}")
            if isinstance(raw, str): return json.loads(raw)
            if isinstance(raw, dict): return raw
        return {}

    async def close(self) -> None:
        pass


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=SupabaseStorage())
cmd_router = Router()  # Yuqori prioritetli — buyruqlar uchun
router = Router()      # FSM va boshqa handlerlar uchun
app = FastAPI()

def is_command(message: types.Message) -> bool:
    """Xabar slash-buyruq ekanligini tekshiradi"""
    return message.text and message.text.startswith("/")

class OrderForm(StatesGroup):
    name = State()
    phone = State()
    region = State()
    location = State()
    order_type = State()
    categories = State()
    xona_photos = State()
    measurements = State()
    design_photos = State()
    deadline = State()
    password = State()

REGIONS = {
    "01 - Toshkent sh": "01", "10 - Toshkent v": "10", "40 - Farg'ona": "40", 
    "60 - Andijon": "60", "50 - Namangan": "50", "20 - Sirdaryo": "20", 
    "25 - Jizzax": "25", "30 - Samarqand": "30", "80 - Buxoro": "80", 
    "85 - Navoiy": "85", "70 - Qashqadaryo": "70", "75 - Surxondaryo": "75", 
    "90 - Xorazm": "90", "95 - Qoraqalpog'iston": "95"
}

def skip_kb(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⏭ O'tkazib yuborish"), KeyboardButton(text="➡️ Davom etish")]], resize_keyboard=True)
def next_kb(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➡️ Davom etish")]], resize_keyboard=True)
def loc_kb(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Lokatsiya yuborish", request_location=True)]], resize_keyboard=True)
def order_type_kb(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Erkin")], [KeyboardButton(text="Joyga moslangan")]], resize_keyboard=True)

def region_kb():
    keys = list(REGIONS.keys())
    kb = []
    for i in range(0, len(keys), 2):
        row = [KeyboardButton(text=keys[i])]
        if i+1 < len(keys): row.append(KeyboardButton(text=keys[i+1]))
        kb.append(row)
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def generate_items_keyboard(items: dict):
    buttons = []
    for k, v in items.items():
        buttons.append([
            InlineKeyboardButton(text="➖", callback_data=f"cat_sub_{k}"),
            InlineKeyboardButton(text=f"{k}: {v} ta", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"cat_add_{k}")
        ])
    buttons.append([InlineKeyboardButton(text="✅ Davom etish", callback_data="cat_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_status_board(order, employees):
    emp_name = employees.get(str(order.get('employee_id')), 'Noma''lum')
    
    cat_texts = []
    if isinstance(order.get('categories'), dict):
        for k, v in order['categories'].items():
            if v > 0: cat_texts.append(f"{k}: {v}")
    elif isinstance(order.get('categories'), list):
        cat_texts = order['categories']
    cat_text = ", ".join(cat_texts) if cat_texts else "Yo'q"
    
    loc_display = f"<a href='https://t.me/Maryam_mebel_bot?start=loc_{order['id']}'>[📍 Lokatsiya mavjud]</a>" if "lat" in str(order.get('location_data','')) or order.get('location_data') else order.get('location', 'Noma''lum')
    
    msg_text = f"🆕 <b>YANGI BUYURTMA</b>\n\n🆔 ID: <code>{order['id']}</code>\n👤 Mijoz: {order['customer_name']}\n📞 Tel: {order['phone']}\n📍 Manzil: {loc_display}\n📦 Kategoriyalar: {cat_text}\n📏 O'lcham: {order.get('measurements', 'Faqat rasm')}\n⏳ Muddat: {order.get('deadline', 'Neizvestno')}\n👷‍♂️ <b>Qabul qildi:</b> {emp_name}\n\nStatus:\n"
    
    status_order = ["Savatda", "Texnologda", "Taminotchida", "Ishlab chiqarishda", "Yetkazishda", "O'rnatishda", "Topshirilgan"]
    history = order.get('status_timestamps', {})
    
    for st in status_order:
        if st in history:
            time_str = history[st]
            is_active = (order['status'] == st)
            is_error = (order['status'] == "Xatolik sabab toxtab qolgan")
            
            icon = "✅aktiv" if is_active else ""
            if is_error and st == list(history.keys())[-1]: icon = "🚩xatolik"
            msg_text += f"|  {st}  -  {time_str}      {icon}\n"
    
    return msg_text

def get_status_markup(order):
    status = order.get('status')
    order_id = order['id']
    
    buttons = []
    status_order = ["Savatda", "Texnologda", "Taminotchida", "Ishlab chiqarishda", "Yetkazishda", "O'rnatishda", "Topshirilgan"]
    
    if status == "Xatolik sabab toxtab qolgan":
        buttons.append([InlineKeyboardButton(text="🔄 Aktivlashtirish (Tiklash)", callback_data=f"st_Aktiv_{order_id}")])
    elif status == "Topshirilgan":
        pass
    else:
        next_st = ""
        try:
            curr_idx = status_order.index(status)
            if curr_idx < len(status_order) - 1: next_st = status_order[curr_idx + 1]
        except:
            next_st = "Texnologda"
            
        if next_st:
            buttons.append([InlineKeyboardButton(text=f"Keyingi: {next_st} ➡️", callback_data=f"st_{next_st}_{order_id}")])
        buttons.append([InlineKeyboardButton(text="🛑 STOP (Xatolik)", callback_data=f"st_Xatolik_{order_id}")])
        
        if status in ["Savatda", "Texnologda", "Taminotchida"]:
            buttons.append([InlineKeyboardButton(text="📝 Tahrirlash (Kategoriya/Miqdor)", url=f"https://t.me/Maryam_mebel_bot?start=edit_{order_id}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

@cmd_router.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    # Har qanday /start buyrug'i avvalgi FSM holatini tozalaydi
    await state.clear()
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        if param.startswith("loc_"):
            order_id = param.replace("loc_", "")
            res = supabase.table("orders").select("location_data, location").eq("id", order_id).execute()
            if res.data:
                loc = res.data[0].get('location_data')
                if loc and "lat" in loc:
                    await message.answer_location(latitude=float(loc['lat']), longitude=float(loc['long']))
                elif loc:
                    await message.answer(f"Lokatsiya: {loc}")
                else:
                    await message.answer("Aniq lokatsiya jo'natilmagan.")
            return
        elif param.startswith("edit_"):
            if message.from_user.id not in ADMIN_USERS:
                await message.answer("Sizda tahrirlash huquqi yo'q!")
                return
            order_id = param.replace("edit_", "")
            await message.answer(f"Ushbu buyurtmani tahrirlamoqchisiz: {order_id}\n\nTizim hali faollashtirilmadi.")
            return
            
    await message.answer("Assalomu alaykum, Maryam Mebel botiga xush kelibsiz!\nBuyurtma berish uchun /new_order buyrug'ini bosing.", reply_markup=ReplyKeyboardRemove())

@cmd_router.message(Command("new_order"))
async def new_order_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(categories={"Shkaf": 0, "Krovat": 0, "Parta": 0, "Komod": 0}, xona=[], zamer=[], dizayn=[])
    await message.answer("Buyurtmachi ismi:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.name)

@router.message(OrderForm.name)
async def process_name(message: types.Message, state: FSMContext):
    if is_command(message): return
    await state.update_data(name=message.text)
    await message.answer("Buyurtmachi telefon raqami:")
    await state.set_state(OrderForm.phone)

@router.message(OrderForm.phone)
async def process_phone(message: types.Message, state: FSMContext):
    if is_command(message): return
    await state.update_data(phone=message.text)
    await message.answer("Viloyatni tanlang:", reply_markup=region_kb())
    await state.set_state(OrderForm.region)

@router.message(OrderForm.region)
async def process_region(message: types.Message, state: FSMContext):
    if is_command(message): return
    r_code = REGIONS.get(message.text, "00")
    await state.update_data(region_code=r_code, region_name=message.text)
    await message.answer("O'rnatish manzili:", reply_markup=loc_kb())
    await state.set_state(OrderForm.location)

@router.message(OrderForm.location)
async def process_location(message: types.Message, state: FSMContext):
    if is_command(message): return
    loc_data = None
    sdata = await state.get_data()
    r_name = sdata.get('region_name', '')
    
    if message.location:
        loc_text = f"{r_name} (Xaritalangan joy)"
        loc_data = {"lat": message.location.latitude, "long": message.location.longitude}
    else:
        loc_text = f"{r_name}, {message.text}"
        loc_data = loc_text
        
    await state.update_data(location=loc_text, location_data=loc_data)
    await message.answer("Buyurtma turi:", reply_markup=order_type_kb())
    await state.set_state(OrderForm.order_type)

@router.message(OrderForm.order_type)
async def process_otype(message: types.Message, state: FSMContext):
    if is_command(message): return
    otype = message.text if message.text in ["Erkin", "Joyga moslangan"] else "Joyga moslangan"
    await state.update_data(order_type=otype)
    sdata = await state.get_data()
    cats = sdata.get("categories")
    await message.answer("Mahsulotlarni va sonini belgilang:", reply_markup=generate_items_keyboard(cats))
    await state.set_state(OrderForm.categories)

@router.callback_query(OrderForm.categories, F.data.startswith("cat_"))
async def process_cats(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    action = data[1]
    sdata = await state.get_data()
    cats = sdata.get("categories", {})
    
    if action == "done":
        total = sum(cats.values())
        if total == 0:
            await callback.answer("Kamida 1 ta musiqa!... adashdim kategoriya", show_alert=True) # joke for bot :)
            return
        await callback.message.delete()
        
        otypes = sdata.get("order_type", "")
        sm = next_kb() if otypes == "Joyga moslangan" else skip_kb()
        req_text = "DIQQAT: Joyga moslangan mebel uchun Xona rasmi majburiy!" if otypes == "Joyga moslangan" else "(Erkin mebel bo'lsa O'tkazib yuborishingiz mumkin)"
        
        await callback.message.answer(f"Tanlandi.\n\nEndi Xona rasmlarini yuboring. {req_text}", reply_markup=sm)
        await state.set_state(OrderForm.xona_photos)
        return
        
    item = data[2]
    if action == "add": cats[item] += 1
    elif action == "sub" and cats[item] > 0: cats[item] -= 1
    await state.update_data(categories=cats)
    try: await callback.message.edit_reply_markup(reply_markup=generate_items_keyboard(cats))
    except: pass
    await callback.answer()

@router.message(OrderForm.xona_photos)
async def process_xona(message: types.Message, state: FSMContext):
    if is_command(message): return
    sdata = await state.get_data()
    if message.text in ["⏭ O'tkazib yuborish", "➡️ Davom etish"]:
        if sdata.get("order_type") == "Joyga moslangan" and not sdata.get("xona") and message.text == "⏭ O'tkazib yuborish":
            await message.answer("Joyga moslangan buyurtmada xona rasmi MAJBURIY. Rasm yuklang!")
            return
        await message.answer("O'lchamlar (Zamer) rasmini yoki ma'lumotlarini yuboring:", reply_markup=next_kb())
        await state.set_state(OrderForm.measurements)
        return
    if message.photo:
        xona = sdata.get("xona", [])
        xona.append(message.photo[-1].file_id)
        await state.update_data(xona=xona)

@router.message(OrderForm.measurements)
async def process_measurements(message: types.Message, state: FSMContext):
    if is_command(message): return
    sdata = await state.get_data()
    if message.text == "➡️ Davom etish":
        if not sdata.get("zamer") and not sdata.get("zamer_text"):
            await message.answer("Iltimos, zamer kiritilmadi!")
            return
        await message.answer("Dizayn namunalarini yuboring:", reply_markup=skip_kb())
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
    if is_command(message): return
    if message.text in ["⏭ O'tkazib yuborish", "➡️ Davom etish"]:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="10 kun"), KeyboardButton(text="15 kun")],[KeyboardButton(text="20 kun"), KeyboardButton(text="Aniqlanmagan")]], resize_keyboard=True)
        await message.answer("Qat'iy muddatni tanlang:", reply_markup=kb)
        await state.set_state(OrderForm.deadline)
        return
    if message.photo:
        sdata = await state.get_data()
        dizayn = sdata.get("dizayn", [])
        dizayn.append(message.photo[-1].file_id)
        await state.update_data(dizayn=dizayn)

@router.message(OrderForm.deadline)
async def process_deadline(message: types.Message, state: FSMContext):
    if is_command(message): return
    deadline = message.text
    if message.text == "Aniqlanmagan": deadline = "Neizvestno"
    await state.update_data(deadline=deadline)
    await message.answer("Tasdiqlash uchun Maxsus Parolingizni kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderForm.password)

def get_now_str():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    return now.strftime("%H:%M | %d.%m.%Y")

def generate_order_id(region_code, cats_dict):
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    date_str = now.strftime("%d%m") # DDMM (e.g. 2304)
    c1 = "1" if cats_dict.get("Shkaf", 0) > 0 else "0"
    c2 = "1" if cats_dict.get("Krovat", 0) > 0 else "0"
    c3 = "1" if cats_dict.get("Parta", 0) > 0 else "0"
    c4 = "1" if cats_dict.get("Komod", 0) > 0 else "0"
    cat_str = f"{c1}{c2}{c3}{c4}"
    uid = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"{region_code}-{date_str}-{cat_str}-{uid}"

@router.message(OrderForm.password)
async def process_password(message: types.Message, state: FSMContext):
    if is_command(message): return
    pwd = message.text
    if not supabase: return
    res = supabase.table("employees").select("*").eq("password", pwd).execute()
    if not res.data:
        await message.answer("Noto'g'ri parol! Qaytadan kiriting:")
        return
    employee = res.data[0]
    sdata = await state.get_data()
    
    timestamp_str = get_now_str()
    status_history = {"Savatda": timestamp_str}
    
    order_id = generate_order_id(sdata.get('region_code', '00'), sdata['categories'])
    
    try:
        ins = supabase.table("orders").insert({
            "id": order_id,
            "customer_name": sdata['name'],
            "phone": sdata['phone'],
            "location": sdata['location'],
            "location_data": sdata['location_data'],
            "order_type": sdata['order_type'],
            "categories": sdata['categories'],
            "measurements": sdata.get('zamer_text', "Rasm orqali berilgan"),
            "deadline": sdata['deadline'],
            "employee_id": employee['id'],
            "status": "Savatda",
            "status_timestamps": status_history
        }).execute()
        
        order_row = ins.data[0]
        
        for group, items in [('xona', sdata['xona']), ('zamer', sdata['zamer']), ('dizayn', sdata['dizayn'])]:
            for fid in items:
                supabase.table("order_media").insert({"order_id": order_id, "media_type": group, "file_id": fid}).execute()
    except Exception as e:
        await message.answer(f"Xatolik saqlashda: {e}")
        return
        
    t_order = int(TOPIC_ORDER) if TOPIC_ORDER else None
    
    emp_map = {str(employee['id']): employee['name']}
    msg_text = get_status_board(order_row, emp_map)
    status_kb = get_status_markup(order_row)
    
    media_msg_ids = []
    
    try:
        msg = await bot.send_message(chat_id=GROUP_ID, message_thread_id=t_order, text=msg_text, reply_markup=status_kb, disable_web_page_preview=True)
        supabase.table("orders").update({"group_message_id": msg.message_id}).eq("id", order_id).execute()
    except Exception as e: pass
        
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
            sent = await bot.send_media_group(chat_id=GROUP_ID, media=media, message_thread_id=tid)
            for m in sent:
                media_msg_ids.append(m.message_id)
        except Exception as e: pass

    await send_group_to_topic(TOPIC_XONA, "xona", "XONA RASMLARI", sdata['xona'])
    await send_group_to_topic(TOPIC_ZAMER, "zamer", "O'LCHAMLAR (ZAMER)", sdata['zamer'])
    await send_group_to_topic(TOPIC_DESIGN, "dizayn", "DIZAYN NAMUNALARI", sdata['dizayn'])
    
    # Rasm xabarlarining ID larini bazaga saqlaymiz
    if media_msg_ids:
        supabase.table("orders").update({"group_media_msg_ids": media_msg_ids}).eq("id", order_id).execute()
    
    await message.answer(f"✅ Barcha ma'lumot qabul qilindi. Buyurtma ID: {order_id}")
    await state.clear()

@router.callback_query(F.data.startswith("st_"))
async def update_status_cb(callback: CallbackQuery):
    # Faqat ruxsat berilgan adminlar status o'zgartira oladi
    if callback.from_user.id not in ADMIN_USERS:
        await callback.answer("⛔ Sizda buyurtma statusini o'zgartirish huquqi yo'q!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    action = parts[1]
    order_id = parts[2]
    
    res = supabase.table("orders").select("*, employees(name)").eq("id", order_id).execute()
    if not res.data:
        await callback.answer("Topilmadi", show_alert=True)
        return
    order = res.data[0]
    
    new_status = action
    if action == "Xatolik": new_status = "Xatolik sabab toxtab qolgan"
    elif action == "Aktiv":
        hist = order.get("status_timestamps", {})
        keys = list(hist.keys())
        if "Xatolik sabab toxtab qolgan" in keys: keys.remove("Xatolik sabab toxtab qolgan")
        new_status = keys[-1] if keys else "Savatda"
        
    timestamp_str = get_now_str()
    history = order.get("status_timestamps", {})
    history[new_status] = timestamp_str
    
    supabase.table("orders").update({"status": new_status, "status_timestamps": history}).eq("id", order_id).execute()
    order["status"] = new_status
    order["status_timestamps"] = history
    
    emp_map = {str(order.get('employee_id')): order.get('employees', {}).get('name', '')}
    msg_text = get_status_board(order, emp_map)
    status_kb = get_status_markup(order)
    
    try:
        if order.get("group_message_id"):
            await bot.edit_message_text(text=msg_text, chat_id=GROUP_ID, message_id=order["group_message_id"], reply_markup=status_kb, disable_web_page_preview=True)
    except Exception as e: pass
    
    # Yangi statusga mos topicga bildirishnoma yuboramiz
    topic_id = STATUS_TOPIC_MAP.get(new_status)
    if topic_id:
        try:
            notify_text = (f"📢 <b>Status yangilandi</b>\n\n"
                           f"🆔 <code>{order_id}</code>\n"
                           f"👤 {order.get('customer_name', '')}\n"
                           f"📦 {new_status}\n"
                           f"⏰ {timestamp_str}")
            await bot.send_message(chat_id=GROUP_ID, message_thread_id=int(topic_id), text=notify_text)
        except Exception:
            pass
        
    await callback.answer(f"Status yangilandi: {new_status}")

@cmd_router.message(Command("buyurtmalar"))
async def list_orders(message: types.Message, state: FSMContext):
    await state.clear()
    if not supabase: return
    res = supabase.table("orders").select("id, customer_name, status, deadline").neq("status", "Topshirilgan").execute()
    if not res.data:
        await message.answer("Faol buyurtmalar yo'q.")
        return
    text = "📋 <b>Faol Buyurtmalar:</b>\n\n"
    for o in res.data:
        text += f"🆔 <code>/order_{o['id'].replace('-','_')}</code>\n👤 {o['customer_name']} - <b>{o['status']}</b> ({o['deadline']})\n\n"
    await message.answer(text)

@router.message(F.text.startswith("/order_"))
async def view_order(message: types.Message):
    if not supabase: return
    # Transform /order_40_2304_1100_XYZ to 40-2304-1100-XYZ
    short_id = message.text.replace("/order_", "")
    # Due to _ replacing -, we can do a broad match or exact if we use UUID.
    # We replaced - with _ simply because telegram commands don't support -.
    actual_id = short_id.replace("_", "-")
    
    res = supabase.table("orders").select("*, employees(name)").eq("id", actual_id).execute()
    if not res.data:
        await message.answer("Buyurtma topilmadi.")
        return
    order = res.data[0]
    emp_map = {str(order.get('employee_id')): order.get('employees', {}).get('name', '')}
    
    msg_text = get_status_board(order, emp_map)
    status_kb = get_status_markup(order)
    
    await message.answer(msg_text, reply_markup=status_kb, disable_web_page_preview=True)

@cmd_router.message(Command("clear"))
async def clear_data(message: types.Message):
    # Faqat shaxsiy chatda ishlaydi
    if message.chat.type != "private":
        return
    # Faqat admin
    if message.from_user.id not in ADMIN_USERS:
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q!")
        return
    if not supabase:
        await message.answer("Baza ulanmagan.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, barchasini o'chir", callback_data="confirm_clear")],
        [InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data="cancel_clear")]
    ])
    await message.answer("⚠️ DIQQAT!\n\nBarcha buyurtmalar, rasmlar va FSM holatlari o'chiriladi.\nBu amalni ortga qaytarib bo'lmaydi!\n\nDavom etasizmi?", reply_markup=kb)

@router.callback_query(F.data == "confirm_clear")
async def confirm_clear(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_USERS:
        await callback.answer("⛔ Huquq yo'q!", show_alert=True)
        return
    try:
        await callback.message.edit_text("🔄 Guruh postlari o'chirilmoqda...")
        
        # Avval guruhdagi postlarni o'chiramiz (buyurtma posti + rasm postlari)
        try:
            orders = supabase.table("orders").select("group_message_id, group_media_msg_ids").execute()
        except Exception:
            orders = supabase.table("orders").select("group_message_id").execute()
        deleted = 0
        failed = 0
        for o in orders.data:
            # Asosiy buyurtma posti
            msg_id = o.get("group_message_id")
            if msg_id:
                try:
                    await bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                    deleted += 1
                except Exception:
                    failed += 1
            # Rasm postlari
            media_ids = o.get("group_media_msg_ids", []) or []
            for mid in media_ids:
                try:
                    await bot.delete_message(chat_id=GROUP_ID, message_id=mid)
                    deleted += 1
                except Exception:
                    failed += 1
        
        # Keyin bazani tozalaymiz
        supabase.table("order_media").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        supabase.table("orders").delete().neq("id", "---").execute()
        supabase.table("fsm_states").delete().neq("chat_id", 0).execute()
        
        await callback.message.edit_text(f"🗑 Tozalandi!\n\n📨 Guruhdan o'chirildi: {deleted} ta xabar\n⚠️ O'chirib bo'lmadi: {failed} ta\n🗄 Baza: buyurtmalar, rasmlar, FSM — hammasi tozalandi!")
    except Exception as e:
        await callback.message.edit_text(f"Xatolik: {e}")
    await callback.answer()

@router.callback_query(F.data == "cancel_clear")
async def cancel_clear(callback: CallbackQuery):
    await callback.message.edit_text("Bekor qilindi. Hech narsa o'chirilmadi.")
    await callback.answer()

@cmd_router.message(Command("purge"))
async def purge_group(message: types.Message):
    """Guruhdagi BARCHA xabarlarni o'chiradi (bazadagi va bazada bo'lmaganlarni ham)"""
    if message.chat.type != "private":
        return
    if message.from_user.id not in ADMIN_USERS:
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q!")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, guruhni tozala", callback_data="confirm_purge")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_purge")]
    ])
    await message.answer("🔴 DIQQAT! Bu buyruq guruhdagi BARCHA xabarlarni o'chirishga harakat qiladi.\n\n⚠️ Bot admin bo'lgan va 48 soatdan eski bo'lmagan xabarlar o'chiriladi.\n\nDavom etasizmi?", reply_markup=kb)

@router.callback_query(F.data == "confirm_purge")
async def confirm_purge(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_USERS:
        await callback.answer("⛔ Huquq yo'q!", show_alert=True)
        return
    
    await callback.message.edit_text("🔄 Guruh tozalanmoqda... Bu biroz vaqt olishi mumkin.")
    
    try:
        # Oxirgi xabar ID sini aniqlash uchun vaqtinchalik xabar yuboramiz
        temp_msg = await bot.send_message(chat_id=GROUP_ID, text="🔄 Tozalash jarayoni...")
        last_id = temp_msg.message_id
        await bot.delete_message(chat_id=GROUP_ID, message_id=last_id)
        
        deleted = 0
        failed = 0
        
        # Oxirgi 500 ta xabar ID sini tekshiramiz (orqaga qarab)
        for msg_id in range(last_id, max(last_id - 500, 0), -1):
            try:
                await bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                deleted += 1
            except Exception:
                failed += 1
        
        # Bazani ham tozalaymiz
        if supabase:
            supabase.table("order_media").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            supabase.table("orders").delete().neq("id", "---").execute()
            supabase.table("fsm_states").delete().neq("chat_id", 0).execute()
        
        await callback.message.edit_text(f"🗑 Guruh tozalandi!\n\n📨 O'chirildi: {deleted} ta xabar\n⏭ O'tkazib yuborildi: {failed} ta\n🗄 Baza ham tozalandi!")
    except Exception as e:
        await callback.message.edit_text(f"Xatolik: {e}")
    await callback.answer()

@router.callback_query(F.data == "cancel_purge")
async def cancel_purge(callback: CallbackQuery):
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()

dp.include_router(cmd_router)  # Buyruqlar birinchi tekshiriladi
dp.include_router(router)      # FSM handlerlar ikkinchi

@app.post("/api/webhook")
async def webhook(request: Request):
    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        await dp.feed_update(bot=bot, update=telegram_update)
    except Exception as e: pass
    return {"status": "ok"}
