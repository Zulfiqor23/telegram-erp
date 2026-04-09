-- =====================================
-- Telegram ERP - V2 Kengaytirilgan Baza
-- O'zgarishlar: Auth, Kengaytirilgan buyurtmalar jadvali, Xodimlar
-- =====================================

-- 1. Avvalgi jadvallarni (agar bo'lsa) o'chirib tashlash (xatosiz qayta qurish uchun)
DROP TABLE IF EXISTS "order_media" CASCADE;
DROP TABLE IF EXISTS "orders" CASCADE;
DROP TABLE IF EXISTS "employees" CASCADE;

-- 2. Xodimlar jadvalini yaratish (Adminlar shu yerdan xodim qo'shadi)
CREATE TABLE "employees" (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    password VARCHAR(50) UNIQUE NOT NULL, -- Parol aniq va yagona bo'lishi kerak
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'Asia/Tashkent')
);

-- 3. Buyurtmalar (Orders) jadvalini kengaytirilgan formatda yaratish
CREATE TABLE "orders" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    location TEXT NOT NULL,
    categories JSONB,              -- Tanlangan mahsulot turlari (Shkaf, ... )
    measurements TEXT,             -- O'lchamlar matni yoki ma'lumoti
    deadline VARCHAR(100),         -- Qachonga qilinishi kerakligi
    status VARCHAR(50) DEFAULT 'Savatda', -- Yangi statuslar tizimi
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL, -- Zayavkani olgan xodim (FK)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'Asia/Tashkent')
);

-- 4. Medialar jadvalini saqlab qolish
CREATE TABLE "order_media" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    media_type VARCHAR(50) NOT NULL, -- xona, zamer, dizayn
    file_id TEXT NOT NULL,           -- Telegram file_id
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'Asia/Tashkent')
);

-- 5. Row Level Security (RLS) qoidalari API orqali ishlatilishi uchun
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_media ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all for authenticated or anon service role" ON employees FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all for authenticated or anon service role" ON orders FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Enable all for authenticated or anon service role" ON order_media FOR ALL USING (true) WITH CHECK (true);

-- 6. Dastlabki TEST xodimini qo'shib qo'yamiz (botni test qilish uchun)
-- Ismi: Aziz, Paroli: 1234
INSERT INTO employees (name, phone, password) VALUES ('Test Xodim (Aziz)', '+998901234567', '1234');
