"""
database/setup_db.py
Aroma & Co. — Complete Database Setup
Tables: reservations, menu_items, feedback, chat_logs
Views:  upcoming_bookings, completed_bookings
"""
import sqlite3, os
from datetime import date, timedelta

def create_database():
    print("\n" + "="*55)
    print("  ☕  AROMA & CO. — DATABASE SETUP")
    print("="*55)

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir   = os.path.join(BASE_DIR, "database")
    os.makedirs(db_dir, exist_ok=True)
    db_path  = os.path.join(db_dir, "aroma.db")

    conn = sqlite3.connect(db_path)
    c    = conn.cursor()

    today  = date.today()
    d_today = today.isoformat()
    d_tom   = (today + timedelta(days=1)).isoformat()
    d_2ago  = (today - timedelta(days=2)).isoformat()
    d_3days = (today + timedelta(days=3)).isoformat()
    d_5days = (today + timedelta(days=5)).isoformat()
    d_7days = (today + timedelta(days=7)).isoformat()

    print(f"\n📅 Today: {d_today}")

    # ── RESERVATIONS ────────────────────────────────────────
    print("\n📅 Creating reservations table...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ref         TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            phone       TEXT,
            email       TEXT,
            date        TEXT NOT NULL,
            time        TEXT NOT NULL,
            guests      TEXT NOT NULL,
            special_req TEXT,
            status      TEXT DEFAULT 'Confirmed',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── UPCOMING BOOKINGS VIEW ───────────────────────────────
    print("📈 Creating upcoming_bookings view...")
    c.execute("DROP VIEW IF EXISTS upcoming_bookings")
    c.execute(f"""
        CREATE VIEW upcoming_bookings AS
        SELECT * FROM reservations
        WHERE date >= '{d_today}' AND status = 'Confirmed'
        ORDER BY date, time
    """)

    # ── COMPLETED BOOKINGS VIEW ──────────────────────────────
    print("✅ Creating completed_bookings view...")
    c.execute("DROP VIEW IF EXISTS completed_bookings")
    c.execute(f"""
        CREATE VIEW completed_bookings AS
        SELECT * FROM reservations
        WHERE date < '{d_today}' AND status = 'Confirmed'
        ORDER BY date DESC, time
    """)

    # ── FEEDBACK TABLE ───────────────────────────────────────
    print("⭐ Creating feedback table...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT,
            rating     INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            message    TEXT NOT NULL,
            featured   INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── CHAT LOGS TABLE ──────────────────────────────────────
    print("💬 Creating chat_logs table...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id  TEXT,
            user_msg   TEXT,
            bot_reply  TEXT,
            intent     TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── MENU ITEMS TABLE ────────────────────────────────────
    print("🍽️ Creating menu_items table...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS menu_items (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            category  TEXT NOT NULL,
            name      TEXT NOT NULL,
            desc      TEXT,
            price     INTEGER NOT NULL,
            tag       TEXT,
            is_vegan  INTEGER DEFAULT 0,
            available INTEGER DEFAULT 1
        )
    """)

    # ── SAMPLE DATA ─────────────────────────────────────────
    print("\n📌 Inserting sample reservations...")
    sample_res = [
        ("ARM-0001","Rohit Gupta",   "+91 98765 43210","rohit@email.com",  d_today, "8:00 PM","2 Guests","Window seat",         "Confirmed"),
        ("ARM-0002","Priya Sharma",  "+91 91234 56789","priya@email.com",  d_today, "12:30 PM","4 Guests","Birthday celebration","Confirmed"),
        ("ARM-0003","Arjun Singh",   "+91 99887 76655","arjun@email.com",  d_tom,   "5:00 PM","2 Guests","",                    "Confirmed"),
        ("ARM-0004","Sneha Verma",   "+91 88776 65544","sneha@email.com",  d_tom,   "9:30 AM","3 Guests","Vegan options",       "Confirmed"),
        ("ARM-0005","Rahul Mishra",  "+91 77665 54433","rahul@email.com",  d_2ago,  "8:00 PM","2 Guests","",                    "Cancelled"),
        ("ARM-0006","Nisha Agarwal", "+91 99001 23456","nisha@email.com",  d_3days, "3:30 PM","5 Guests","Private corner",      "Confirmed"),
        ("ARM-0007","Amit Joshi",    "+91 88990 01122","amit@email.com",   d_5days, "7:00 PM","3 Guests","",                    "Confirmed"),
        ("ARM-0008","Kavya Rao",     "+91 70011 22334","kavya@email.com",  d_7days, "1:00 PM","6 Guests","Anniversary dinner",  "Confirmed"),
    ]
    for r in sample_res:
        try:
            c.execute("INSERT INTO reservations (ref,name,phone,email,date,time,guests,special_req,status) VALUES (?,?,?,?,?,?,?,?,?)", r)
        except sqlite3.IntegrityError:
            pass

    # Sample feedback
    print("⭐ Inserting sample feedback...")
    sample_fb = [
        ("Rohit Kumar",   "rohit@email.com",  5, "Absolutely loved the Rose Saffron Latte! Perfect ambience for a date night.", 1),
        ("Priya Sharma",  "",                 5, "Best coffee in Lucknow! The barista workshop was fantastic.", 1),
        ("Arjun Singh",   "arjun@email.com",  4, "Great food and atmosphere. The truffle toast is a must-try!", 1),
        ("Sneha Verma",   "",                 5, "Amazing vegan options. Staff was very accommodating. Will return!"),
        ("Nisha Agarwal", "nisha@email.com",  4, "Love the jazz evenings. Cold brew is excellent. Slight wait on weekends.", 0),
    ]
    for fb in sample_fb:
        try:
            c.execute("INSERT INTO feedback (name,email,rating,message,featured) VALUES (?,?,?,?,?)", fb)
        except:
            pass

    # Sample menu items
    print("🍽️ Inserting menu items...")
    menu = [
        ("Coffee","Espresso Classico","Pure, bold, 25ml Ethiopian blend",120,"",0),
        ("Coffee","Signature Latte","Velvety microfoam, double ristretto",220,"Bestseller",0),
        ("Coffee","Cold Brew Reserve","18-hour slow-steeped Colombian",280,"New",0),
        ("Coffee","Honey Cardamom Flat White","Spiced, golden, comforting",260,"",0),
        ("Coffee","Matcha Cortado","Ceremonial matcha + espresso",290,"Vegan",1),
        ("Coffee","Dark Mocha","72% Valrhona cocoa + espresso",250,"",0),
        ("Food","Butter Croissant","French-style, laminated 27 times",160,"Fresh Daily",0),
        ("Food","Truffle Mushroom Toast","Sourdough, ricotta, wild mushrooms",380,"Bestseller",0),
        ("Food","Seasonal Grain Bowl","Farro, roasted veggies, tahini",350,"Vegan",1),
        ("Food","Eggs Benedict","Poached eggs, hollandaise, smoked salmon",420,"",0),
        ("Food","Brown Butter Banana Cake","Warm slice with vanilla gelato",290,"",0),
        ("Food","Cheese & Charcuterie Board","Seasonal selection, preserves",680,"Sharing",0),
        ("Specials","Rose Saffron Latte","Saffron milk, rose water, pistachio",320,"Seasonal",0),
        ("Specials","Espresso Tonic","Double shot over Indian tonic",300,"New",0),
        ("Specials","Masala Spice Brew","Single origin, fresh spice blend",220,"",0),
        ("Specials","Blueberry Lavender Latte","Blueberry compote, lavender, oat milk",310,"Vegan",1),
        ("Specials","Hojicha Latte","Roasted Japanese green tea",280,"",0),
        ("Specials","Celebration Brunch Set","Coffee, food, dessert, juice for 2",1200,"For 2",0),
        ("Drinks","Sparkling Lemonade","House-pressed lemons, Perrier",180,"",0),
        ("Drinks","Summer Berry Cooler","Strawberry, raspberry, elderflower",220,"New",0),
        ("Drinks","Alphonso Mango Lassi","Real Alphonso mangoes, yoghurt",200,"",0),
        ("Drinks","Single Estate Darjeeling","First flush, muscatel notes",160,"Organic",0),
        ("Drinks","Fresh Pressed Juice","Seasonal selection",160,"",0),
        ("Drinks","House Kombucha","Ginger-lemon, brewed in-house",240,"Probiotic",0),
    ]
    for item in menu:
        try:
            c.execute("INSERT INTO menu_items (category,name,desc,price,tag,is_vegan) VALUES (?,?,?,?,?,?)", item)
        except:
            pass

    conn.commit()
    conn.close()

    print("\n" + "="*55)
    print("  ✅  DATABASE READY!")
    print("="*55)
    print(f"  Path     : {db_path}")
    print(f"  Tables   : reservations, menu_items, feedback, chat_logs")
    print(f"  Views    : upcoming_bookings, completed_bookings")
    print(f"  Bookings : {len(sample_res)} sample entries")
    print("="*55 + "\n")

if __name__ == "__main__":
    create_database()