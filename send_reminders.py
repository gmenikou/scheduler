import json, os, sys, datetime, unicodedata
import urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

MUSIC_FILE = "reminder.mp3"  # "" = no music

WEEKDAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

# Manual fixes for names that the automatic rule gets wrong, e.g.
# NAME_OVERRIDES = {"Παναγιώτης": "Παναγιώτη"}
NAME_OVERRIDES = {}


def norm(s):
    return unicodedata.normalize("NFC", str(s)).strip()


def vocative(name):
    """Greek vocative for the greeting: Αλέξανδρος -> Αλέξανδρε, Έλενα -> Έλενα."""
    name = norm(name)
    if name in NAME_OVERRIDES:
        return NAME_OVERRIDES[name]
    first = name.split()[0] if name.split() else name
    if first in NAME_OVERRIDES:
        return NAME_OVERRIDES[first]
    if first.endswith("ος"):
        return first[:-2] + "ε"
    if first.endswith("ης"):
        return first[:-2] + "η"
    if first.endswith("ας"):
        return first[:-2] + "α"
    return first


def api_url(method):
    return f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/{method}"


def send(chat_id, text):
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(api_url("sendMessage"), data=body):
            return True
    except urllib.error.HTTPError as e:
        print("Telegram error", e.code, e.read().decode("utf-8", "replace"))
        return False


def send_audio(chat_id, path, caption):
    boundary = "----reminderboundary7d4a"
    with open(path, "rb") as f:
        audio = f.read()
    parts = []
    for name, value in (("chat_id", str(chat_id)), ("caption", caption)):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )
    filename = os.path.basename(path)
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
        f'Content-Type: audio/mpeg\r\n\r\n'.encode("utf-8")
    )
    parts.append(audio)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    req = urllib.request.Request(
        api_url("sendAudio"),
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req):
            return True
    except urllib.error.HTTPError as e:
        print("Telegram audio error", e.code, e.read().decode("utf-8", "replace"))
        return False


def send_reminder(chat_id, text):
    """Audio with the text as caption; falls back to plain text."""
    if MUSIC_FILE and os.path.exists(MUSIC_FILE):
        if send_audio(chat_id, MUSIC_FILE, text):
            return True
        print("Audio failed, falling back to text")
    return send(chat_id, text)


event = os.environ.get("EVENT_NAME", "")
now = datetime.datetime.now(ZoneInfo("Europe/Nicosia"))

# If GitHub starts a scheduled run very late (after midnight),
# count the days from the previous evening's date.
base = now.date()
if event == "schedule" and now.hour < 6:
    base = base - datetime.timedelta(days=1)

live = event == "schedule" or os.environ.get("SEND_LIVE", "").strip().lower() == "true"
admin = os.environ["ADMIN_CHAT_ID"].strip()

override = os.environ.get("INPUT_DATE", "").strip()
if override:
    style_days = {"48h": 2, "24h": 1}.get(os.environ.get("STYLE", "").strip())
    targets = [(datetime.date.fromisoformat(override), style_days)]
else:
    targets = [(base + datetime.timedelta(days=d), d) for d in (2, 1)]

with open("last_schedule_state_cyclic.json", encoding="utf-8") as f:
    data = json.load(f)
ids = {norm(k): v for k, v in json.loads(os.environ["DOCTOR_CHAT_IDS"]).items()}

ok = True
report = []
for target, days in targets:
    label = target.strftime("%d/%m/%Y")
    doctor = data.get("schedule", {}).get(target.isoformat())
    if not doctor:
        print("No doctor assigned for", label)
        report.append(f"{label}: no doctor assigned")
        continue

    name = vocative(doctor)
    day_name = WEEKDAYS[target.weekday()]
    if days == 2:
        text = (f"🗓️ Γεια σου {name}! Σε 2 ημέρες, {day_name} {label}, έχεις εφημερία.🩺 \n"
    elif days == 1:
        text = (f"⏰ Καλησπέρα {name}! Αύριο, {day_name} {label}, έχεις εφημερία.\n"
                f"Καλή ξεκούραση απόψε και καλή δύναμη! 💪🌙")
    else:
        text = f"🩺 Γεια σου {name}! Έχεις εφημερία {day_name} {label}."

    chat = ids.get(norm(doctor))
    if chat is None:
        print("No chat ID for", doctor)
        report.append(f"{label}: {doctor} has NO chat ID in DOCTOR_CHAT_IDS")
    elif live:
        if send_reminder(chat, text):
            print("Sent to", doctor, label)
            report.append(f"SENT to {doctor} ({label})")
            send(admin, f"📋 Copy of the reminder sent to {doctor}:\n\n{text}")
        else:
            ok = False
            report.append(f"FAILED to send to {doctor} ({label})")
    else:
        report.append(f"PREVIEW (not sent): {doctor}, {label}")
        send_reminder(admin, f"🔔 Sample of what {doctor} would receive:\n\n{text}")

if report:
    send(admin, "\n".join(report))

if not ok:
    sys.exit(1)
