# =============================================================
#  actions/actions.py
#  Aroma & Co. Café Chatbot — Rasa + Gemini AI
#
#  Section 1 — Table Reservation (Rasa Form + DB)
#  Section 2 — Slot Availability (Rasa + DB)
#  Section 3 — Cancel Reservation (Rasa + DB)
#  Section 4 — Gemini AI (menu, café info, general chat)
#  Section 5 — Human Escalation
#  Section 6 — Form Validator
# =============================================================

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet
import sqlite3
import logging
import random
import string
import os
import requests
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Gemini API Setup ─────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
)

# ── Café Context for Gemini ──────────────────────────────────
CAFE_CONTEXT = """
You are the friendly virtual assistant for Aroma & Co., an artisan café in Lucknow, India.
Speak warmly, briefly, and helpfully. Use relevant emojis. Never make up prices or items not listed.

=== CAFÉ INFO ===
Name     : Aroma & Co.
Location : 12-A Hazratganj, Lucknow – 226 001
Phone    : +91 98765 43210
Email    : hello@aromaandco.in
Hours    : Mon–Fri 8AM–10PM | Sat–Sun 8AM–11PM
WiFi     : Network: AromaCo_Guests | Password: coffeeislife
Parking  : Hazratganj Parking Complex (2-min walk)
Payment  : Cards, UPI, Cash

=== EVENTS ===
🎷 Live Jazz Night — Every Fri & Sat, 7–10 PM
☕ Barista Workshop — Sundays 10 AM (₹799/person)
🎂 Private Events — up to 30 guests

=== DIETARY ===
Vegan-friendly items | Gluten-free on request | Oat, almond, soy milk available

=== MENU ===
COFFEE: Espresso ₹120 | Latte ₹220 | Cold Brew ₹280 | Flat White ₹260 | Matcha Cortado ₹290 | Dark Mocha ₹250
FOOD: Croissant ₹160 | Truffle Toast ₹380 | Grain Bowl ₹350 | Eggs Benedict ₹420 | Banana Cake ₹290 | Charcuterie ₹680
SPECIALS: Rose Saffron Latte ₹320 | Espresso Tonic ₹300 | Masala Brew ₹220 | Blueberry Latte ₹310 | Hojicha ₹280 | Brunch Set ₹1200
DRINKS: Lemonade ₹180 | Berry Cooler ₹220 | Mango Lassi ₹200 | Darjeeling ₹160 | Fresh Juice ₹160 | Kombucha ₹240

=== RULES ===
- For TABLE RESERVATIONS, SLOT CHECKS, or CANCELLATIONS: tell user those are handled by booking system.
- Keep answers under 120 words unless detailed menu is requested.
- End with a helpful follow-up offer.
"""

# Absolute path — Rasa action server can be run from any directory
# actions.py lives in actions/, go one level up to project root
import pathlib as _pl
DB_PATH = str(_pl.Path(__file__).parent.parent / 'database' / 'aroma.db')


def ask_gemini(user_message: str) -> str:
    """Call Gemini 1.5 Flash API and return response text."""
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return None   # no key set — use fallback

    try:
        payload = {
            "contents": [
                {"role": "user",  "parts": [{"text": f"[SYSTEM]\n{CAFE_CONTEXT}"}]},
                {"role": "model", "parts": [{"text": "Understood! I'm the Aroma & Co. assistant. How can I help? ☕"}]},
                {"role": "user",  "parts": [{"text": user_message}]},
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 300,
                "topP": 0.9,
            }
        }

        response = requests.post(
            GEMINI_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            logger.error(f"Gemini error {response.status_code}: {response.text[:200]}")
            return None

    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
#  SECTION 1 — TABLE RESERVATION
# ═══════════════════════════════════════════════════════════════

class ActionReserveTable(Action):
    """Book a café table and save to database."""

    def name(self) -> Text:
        return "action_reserve_table"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        name   = tracker.get_slot("customer_name")
        date   = tracker.get_slot("booking_date")
        time   = tracker.get_slot("booking_time")
        guests = tracker.get_slot("guest_count")

        if not all([name, date, time, guests]):
            dispatcher.utter_message(
                text="I still need your name, preferred date, time, and number of guests."
            )
            return []

        ref = "ARM-" + "".join(random.choices(string.digits, k=4))

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref TEXT UNIQUE, name TEXT, phone TEXT, email TEXT,
                    date TEXT, time TEXT, guests TEXT, special_req TEXT,
                    status TEXT DEFAULT 'Confirmed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute(
                "INSERT INTO reservations (ref,name,date,time,guests) VALUES (?,?,?,?,?)",
                (ref, name, date, time, guests)
            )
            conn.commit()
            conn.close()

            dispatcher.utter_message(text=(
                f"✅ **Table Reserved at Aroma & Co.!**\n\n"
                f"📋 Reference : {ref}\n"
                f"👤 Name      : {name}\n"
                f"📅 Date      : {date}\n"
                f"🕐 Time      : {time}\n"
                f"👥 Guests    : {guests}\n\n"
                f"We look forward to welcoming you! ☕\n"
                f"To modify or cancel, share your reference number here."
            ))

        except Exception as e:
            logger.error(f"Reservation error: {e}")
            dispatcher.utter_message(
                text="Couldn't save your reservation. Please call +91 98765 43210."
            )

        return [
            SlotSet("customer_name", None), SlotSet("booking_date", None),
            SlotSet("booking_time",  None), SlotSet("guest_count",  None),
        ]


# ═══════════════════════════════════════════════════════════════
#  SECTION 2 — SLOT AVAILABILITY
# ═══════════════════════════════════════════════════════════════

class ActionCheckSlots(Action):
    """Show live time-slot availability for a given date."""

    def name(self) -> Text:
        return "action_check_slots"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        date = tracker.get_slot("booking_date")
        ALL  = ["8:00 AM","9:30 AM","11:00 AM","12:30 PM",
                "2:00 PM","3:30 PM","5:00 PM","6:30 PM","8:00 PM"]
        MAX  = 4

        if not date:
            dispatcher.utter_message(
                text="Our daily slots: " + "  •  ".join(ALL) +
                     "\n\nShare your preferred date and I'll check live availability!"
            )
            return []

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "SELECT time, COUNT(*) FROM reservations "
                "WHERE date=? AND status!='Cancelled' GROUP BY time",
                (date,)
            )
            booked = {r[0]: r[1] for r in c.fetchall()}
            conn.close()

            avail = [s for s in ALL if booked.get(s, 0) < MAX]
            full  = [s for s in ALL if booked.get(s, 0) >= MAX]

            if avail:
                msg = f"Available on **{date}**:\n" + "\n".join(f"  ✅ {s}" for s in avail)
                if full:
                    msg += "\n\nFully booked:\n" + "\n".join(f"  ❌ {s}" for s in full)
                msg += "\n\nWhich time works best for you?"
            else:
                msg = f"All slots on {date} are fully booked. Would you like another date?"

            dispatcher.utter_message(text=msg)

        except Exception:
            dispatcher.utter_message(
                text="Available slots: 8 AM, 9:30 AM, 12:30 PM, 3:30 PM, 5 PM, 8 PM."
            )
        return []


# ═══════════════════════════════════════════════════════════════
#  SECTION 3 — CANCEL RESERVATION
# ═══════════════════════════════════════════════════════════════

class ActionCancelReservation(Action):
    """Cancel a reservation by ARM- reference."""

    def name(self) -> Text:
        return "action_cancel_reservation"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        ref = tracker.get_slot("booking_ref")

        if not ref:
            dispatcher.utter_message(
                text="Please share your booking reference (e.g. ARM-1234)."
            )
            return []

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                "UPDATE reservations SET status='Cancelled' WHERE ref=?",
                (ref.upper(),)
            )
            conn.commit()
            affected = c.rowcount
            conn.close()

            if affected:
                dispatcher.utter_message(
                    text=f"✅ Reservation **{ref.upper()}** cancelled. Hope to see you another time! ☕"
                )
            else:
                dispatcher.utter_message(
                    text=f"No reservation found with ref **{ref}**. Please call +91 98765 43210."
                )
        except Exception as e:
            logger.error(f"Cancel error: {e}")
            dispatcher.utter_message(text="Unable to cancel. Please call +91 98765 43210.")

        return [SlotSet("booking_ref", None)]


# ═══════════════════════════════════════════════════════════════
#  SECTION 4 — GEMINI AI (menu, info, general chat)
# ═══════════════════════════════════════════════════════════════

MENU_FALLBACK = """Here's our menu:\n\n☕ **Coffee** — Espresso ₹120 to Matcha Cortado ₹290\n🥐 **Food** — Croissant ₹160 to Charcuterie ₹680\n🌸 **Specials** — Rose Saffron Latte, Espresso Tonic & more\n🍹 **Drinks** — Lassi, Kombucha, Darjeeling from ₹160\n\nAsk about any item for details! 😊"""

INFO_FALLBACK = """**Aroma & Co.:**\n📍 12-A Hazratganj, Lucknow\n🕐 Mon–Fri: 8AM–10PM | Sat–Sun: 8AM–11PM\n📞 +91 98765 43210\n📧 hello@aromaandco.in\n📶 WiFi: AromaCo_Guests | coffeeislife"""

GREET_FALLBACK = """Hello! ☕ Welcome to Aroma & Co.\n\nI can help you with:\n📅 Table reservations\n☕ Menu & prices\n🕐 Hours & location\n🎷 Events & workshops\n\nWhat would you like to know?"""


class ActionGeminiResponse(Action):
    """
    Handles all conversational queries via Gemini AI.
    Falls back to static responses if API key not set.
    """

    def name(self) -> Text:
        return "action_gemini_response"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_text = tracker.latest_message.get("text", "")
        intent    = tracker.latest_message.get("intent", {}).get("name", "")

        reply = ask_gemini(user_text)

        if reply:
            dispatcher.utter_message(text=reply)
        else:
            # Static fallback by intent
            if intent in ("menu_info", "ask_price", "check_availability"):
                dispatcher.utter_message(text=MENU_FALLBACK)
            elif intent == "cafe_info":
                dispatcher.utter_message(text=INFO_FALLBACK)
            elif intent == "greet":
                dispatcher.utter_message(text=GREET_FALLBACK)
            elif intent == "mood_unhappy":
                dispatcher.utter_message(
                    text="A warm cup of coffee fixes everything! ☕ Come visit us. 😊"
                )
            else:
                dispatcher.utter_message(
                    text="I'm here to help with anything about Aroma & Co.! ☕\n\n"
                         "Ask me about menu, bookings, hours, events, or WiFi."
                )
        return []


# ═══════════════════════════════════════════════════════════════
#  SECTION 5 — HUMAN ESCALATION
# ═══════════════════════════════════════════════════════════════

class ActionHumanHandoff(Action):
    """Connect user to a live team member."""

    def name(self) -> Text:
        return "action_human_handoff"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text=(
            f"👤 **Connecting you to our team...**\n\n"
            f"Session ID : CHT-{tracker.sender_id[:8].upper()}\n\n"
            f"📞 +91 98765 43210\n"
            f"📧 hello@aromaandco.in\n\n"
            f"A team member will be with you shortly. Avg. wait: 2–3 minutes."
        ))
        return []


# ═══════════════════════════════════════════════════════════════
#  SECTION 6 — FORM VALIDATOR
# ═══════════════════════════════════════════════════════════════

class ValidateReservationForm(FormValidationAction):
    """Validate café reservation form slots."""

    def name(self) -> Text:
        return "validate_reservation_form"

    def validate_booking_date(self, slot_value, dispatcher, tracker, domain):
        if slot_value:
            return {"booking_date": slot_value}
        dispatcher.utter_message(text="Please provide a valid date (e.g. 'tomorrow' or '25 March').")
        return {"booking_date": None}

    def validate_guest_count(self, slot_value, dispatcher, tracker, domain):
        try:
            n = int(str(slot_value).strip().split()[0])
            if 1 <= n <= 20:
                return {"guest_count": str(n)}
            dispatcher.utter_message(text="We can accommodate 1–20 guests. How many in your group?")
            return {"guest_count": None}
        except (ValueError, IndexError):
            dispatcher.utter_message(text="How many guests will be joining you?")
            return {"guest_count": None}