# ☕ Aroma & Co. — AI-Powered Café Chatbot

> B.Tech Final Year Project | BBDU Lucknow | June 2026

A full-stack AI chatbot and reservation management system for an artisan café,
built with Rasa NLU + Google Gemini 1.5 Flash + Flask + SQLite.

## 🚀 Features
- 🤖 AI Chatbot (Rasa 3.6 + Gemini fallback) — 95.1% intent accuracy
- 📅 Conversational table booking (5-step FSM)
- 🔍 Real-time booking tracker (/track)
- 👑 Role-based admin dashboard (Admin / Staff)
- ⭐ Customer feedback + testimonials pipeline
- 📧 HTML email confirmations

## 🛠️ Tech Stack
Python 3.9 | Rasa 3.6.21 | Flask 2.3 | SQLite | Google Gemini API | JavaScript

## ⚙️ Quick Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install rasa==3.6.21 flask==2.3.0 flask-cors==4.0.0 google-generativeai==0.7.2
python database/setup_db.py
rasa train
```

## ▶️ Run
Open 3 terminals (all with venv active):
- Terminal 1: `rasa run actions`
- Terminal 2: `rasa run --enable-api --cors "*"`
- Terminal 3: `python web_interface/app.py`

Then open: http://localhost:8000

## 👤 Author
Rohit Kumar Gupta — B.Tech CSE — BBDU Lucknow