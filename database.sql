-- Eski jadvallarni ichidagi ma'lumotlari bilan o'chirib tashlash (Faqat test/boshlang'ich jarayonda ishlating)
DROP TABLE IF EXISTS order_media CASCADE;
DROP TABLE IF EXISTS orders CASCADE;

-- orders jadvali (Buyurtmalar mantiqiy asosini saqlaydi)
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    location TEXT,
    items JSONB DEFAULT '{}'::jsonb, -- Misol uchun: {"Shkaf": 1, "Oshxona": 2}
    status VARCHAR(50) DEFAULT 'NEW',  -- NEW, MEASUREMENT, PRODUCTION, DONE
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC' + interval '5 hours')
);

-- order_media jadvali (Yuklangan har qanday rasm faylini va ularning xarakterini saqlaydi)
CREATE TABLE order_media (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    media_type VARCHAR(50) NOT NULL, -- xona, zamer, dizayn, smeta
    file_id TEXT NOT NULL,           -- Telegram file_id
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC' + interval '5 hours')
);

-- RLS (Row Level Security) qoidalari - API orqali yozish/o'qishga ruxsat berish
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_media ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all for authenticated service role" ON orders FOR ALL 
USING (true) WITH CHECK (true);

CREATE POLICY "Enable all for authenticated service role" ON order_media FOR ALL 
USING (true) WITH CHECK (true);
