import re
import smtplib
import time
from email.mime.text import MIMEText
from urllib.parse import quote_plus

import streamlit as st
from google import genai
from google.genai import types

from prompts import (
    FIRST_PHOTO_NOTE,
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)

MODEL_NAME = st.secrets.get("GEMINI_MODEL", "gemini-3.8-flash")
IMAGE_MODEL = st.secrets.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
OCCASIONS = [
    "Daily / Normal",
    "Wedding",
    "Sports / Gym",
    "Temple visit",
    "Party",
    "Office / College",
    "Festival",
]

st.set_page_config(page_title="StyleSnap", page_icon="👗")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()


def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])
        elif message["kind"] == "links":
            st.caption("🔎 See real photos of this look:")
            for idea in message["content"]:
                url = "https://www.google.com/search?tbm=isch&q=" + quote_plus(idea)
                st.markdown(f"- [{idea}]({url})")


def split_ideas(text):
    """Pull the 'IMAGE_IDEAS: a | b | c' line out of a reply. Returns (clean_text, ideas)."""
    ideas = []
    for match in re.finditer(r"^.*IMAGE_IDEAS\s*:\s*(.+)$", text, flags=re.MULTILINE):
        for idea in match.group(1).split("|"):
            idea = idea.strip(" *`\"'")
            if idea:
                ideas.append(idea)
    clean = re.sub(r"^.*IMAGE_IDEAS\s*:.*$", "", text, flags=re.MULTILINE).strip()
    return clean, ideas[:3]


def generate_outfit_image(description):
    """Ask Gemini to draw the outfit. Returns image bytes, or None if it isn't available."""
    try:
        response = gemini_client.models.generate_content(
            model=IMAGE_MODEL,
            contents=(
                "A realistic full-body fashion photo of an Indian person wearing: "
                f"{description}. Clean studio background, no text, no watermark."
            ),
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                return part.inline_data.data
    except Exception:
        return None
    return None


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_message(st.session_state.messages[-1])


BUSY_MARKERS = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "overloaded")


def ask_gemini(parts):
    """Returns (ok, text). Retries a few times when Gemini is busy (503/429)."""
    last_error = None
    for attempt in range(4):
        try:
            reply = st.session_state.chat.send_message(parts).text
            if reply:
                return True, reply
            last_error = "Empty reply from Gemini"
        except Exception as error:
            last_error = str(error)
        if attempt < 3 and any(m in str(last_error) for m in BUSY_MARKERS + ("Empty",)):
            time.sleep(3 * (attempt + 1))  # wait 3s, 6s, 9s then try again
            continue
        break
    if any(m in str(last_error) for m in BUSY_MARKERS):
        return False, "Gemini is very busy right now. Please wait a minute and try again 🙏"
    return False, f"Sorry, something went wrong: {last_error}"


def send_email(to_address, subject, body):
    try:
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = GMAIL_ADDRESS
        message["To"] = to_address
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        return True, "sent"
    except Exception as error:
        return False, str(error)


# Step 1: onboarding
if "onboarded" not in st.session_state:
    st.title("👗 StyleSnap")
    st.caption("Your photo. Your occasion. Your perfect look.")

    with st.form("onboarding_form"):
        name = st.text_input("Your name")
        mobile = st.text_input("Mobile number", placeholder="+91XXXXXXXXXX")
        email = st.text_input("Email (suggestions will be sent here)")
        my_photo = st.file_uploader(
            "Your photo (so I can suggest what suits you)",
            type=["jpg", "jpeg", "png"],
        )
        submitted = st.form_submit_button("Let's go 🚀")

        if submitted:
            if not name.strip() or not mobile.strip() or not email.strip():
                st.warning("Please fill in your name, mobile number and email.")
            elif my_photo is None:
                st.warning("Please upload your photo.")
            elif "@" not in email:
                st.warning("Please enter a valid email address.")
            else:
                st.session_state.name = name.strip()
                st.session_state.mobile = mobile.strip()
                st.session_state.email = email.strip()
                st.session_state.profile_photo = my_photo.getvalue()
                st.session_state.profile_mime = my_photo.type
                st.session_state.photo_sent = False
                st.session_state.chat = gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                st.session_state.messages = []
                st.session_state.onboarded = True
                st.rerun()
    st.stop()

# Step 2: chat interface
header_col, button_col = st.columns([5, 2], vertical_alignment="center")
with header_col:
    st.title("👗 StyleSnap")
with button_col:
    send_disabled = len(st.session_state.messages) <= 2
    if st.button("📧 Send to Email", disabled=send_disabled, use_container_width=True):
        with st.spinner("Preparing your style summary..."):
            ok, summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
            if ok:
                summary, _ = split_ideas(summary)

                # Add photo-search links for every look suggested in this chat.
                unique_ideas = []
                for idea in st.session_state.get("all_ideas", []):
                    if idea not in unique_ideas:
                        unique_ideas.append(idea)
                links_text = ""
                if unique_ideas:
                    links_text = "\n\n🔎 Photos of these looks:\n" + "\n".join(
                        f"- {idea}: https://www.google.com/search?tbm=isch&q={quote_plus(idea)}"
                        for idea in unique_ideas
                    )

                success, info = send_email(
                    st.session_state.email,
                    f"Your StyleSnap outfit suggestions, {st.session_state.name}",
                    f"Hi {st.session_state.name},\n\n{summary}{links_text}\n\n- StyleSnap 👗",
                )
            else:
                success, info = False, summary  # never email an error message
        if success:
            st.success("Sent! Check your inbox 📬 (also check Spam)")
        else:
            st.error(f"Couldn't send that: {info}")

st.caption(
    f"Logged in as {st.session_state.name} ({st.session_state.mobile}) - "
    f"suggestions go to {st.session_state.email}"
)

occasion = st.selectbox("Occasion", OCCASIONS)
make_image = st.checkbox(
    "🎨 Also generate an AI picture of the outfit (slower)", value=False
)

if not st.session_state.messages:
    add_message("user", "image", st.session_state.profile_photo)
    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name),
    )
else:
    for message in st.session_state.messages:
        render_message(message)

user_input = st.chat_input(
    "Tell me what you need, or attach a photo",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)

if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []

    # Send the user's own profile photo to Gemini once, so it remembers them.
    if not st.session_state.photo_sent:
        parts.append(
            types.Part.from_bytes(
                data=st.session_state.profile_photo,
                mime_type=st.session_state.profile_mime,
            )
        )
        parts.append(FIRST_PHOTO_NOTE)
        sending_profile_photo = True
    else:
        sending_profile_photo = False

    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))

    if text:
        add_message("user", "text", text)
        parts.append(f"[Occasion: {occasion}] {text}")
    elif photo is not None:
        parts.append(
            f"[Occasion: {occasion}] What should I wear? Suggest the outfit, "
            "accessories and footwear."
        )
    else:
        parts.append(
            f"[Occasion: {occasion}] What should I wear? Suggest the outfit, "
            "accessories and footwear."
        )

    with st.spinner("Styling you..."):
        ok, answer = ask_gemini(parts)
    if ok and sending_profile_photo:
        st.session_state.photo_sent = True  # only mark sent once Gemini really got it

    ideas = []
    if ok:
        answer, ideas = split_ideas(answer)
    add_message("assistant", "text", answer)

    if ideas:
        st.session_state.setdefault("all_ideas", []).extend(ideas)  # saved for the email
        add_message("assistant", "links", ideas)
        if make_image:
            with st.spinner("Drawing your outfit..."):
                picture = generate_outfit_image(ideas[0])
            if picture:
                add_message("assistant", "image", picture)
            else:
                add_message(
                    "assistant",
                    "text",
                    "I couldn't generate a picture right now - please use the photo links above 👆",
                )
    st.rerun()