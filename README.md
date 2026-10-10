# 👗 StyleSnap - AI Fashion Stylist

StyleSnap is a Streamlit chat app. The user enters their name, mobile number,
email and a photo once. Then they pick an occasion (wedding, sports, temple
visit, party, daily wear...) and chat with an AI stylist that suggests the
outfit, accessories and footwear that suit them. One button emails the full
list of suggestions to the user.

Built with Gemini (chat + vision) and Gmail SMTP.

## Features
- One-time onboarding (name, mobile, email, photo)
- Occasion selector + free text chat
- Attach extra photos (e.g. an outfit you already own) for feedback
- System prompt keeps the AI on fashion topics only
- "Send to Email" button mails a clean summary

## Run locally
1. `python -m venv venv` and activate it
2. `pip install -r requirements.txt`
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in:
   - Gemini API key from aistudio.google.com
   - Gmail address + App Password (turn on 2-Step Verification, then create it at myaccount.google.com/apppasswords)
4. `streamlit run app.py`

## Deploy
Push to GitHub (never commit `secrets.toml`), then deploy on share.streamlit.io
and paste the secrets in the app's Settings > Secrets.

## Project structure
- `app.py` - the app
- `prompts.py` - the AI's personality and prompts
- `requirements.txt` - dependencies
