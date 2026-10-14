import json, os, sys, datetime, unicodedata
import urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo


def norm(s):
    return unicodedata.normalize("NFC", str(s)).strip()


def send(chat_id, text):
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendMessage"
    try:
        with urllib.request.urlopen(url, data=body):
            return True
    except urllib.error.HTTPError as e:
        print("Telegram error", e.code, e.read().decode("utf-8", "replace"))
        return False


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
    targets = [(datetime.date.fromisoformat(override), None)]
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

    if days == 2:
        text = f"Υπενθύμιση: έχετε εφημερία σε 2 ημέρες, {label}."
    elif days == 1:
        text = f"Υπενθύμιση: έχετε εφημερία αύριο, {label}."
    else:
        text = f"Υπενθύμιση: έχετε εφημερία στις {label}."

    chat = ids.get(norm(doctor))
    if chat is None:
        print("No chat ID for", doctor)
        report.append(f"{label}: {doctor} has NO chat ID in DOCTOR_CHAT_IDS")
    elif live:
        if send(chat, text):
            print("Sent to", doctor, label)
            report.append(f"SENT to {doctor} ({label})")
            send(admin, f"📋 Copy of the reminder sent to {doctor}:\n\n{text}")
        else:
            ok = False
            report.append(f"FAILED to send to {doctor} ({label})")
    else:
        report.append(f"PREVIEW (not sent): {doctor}, {label}: {text}")

if report:
    send(admin, "\n".join(report))

if not ok:
    sys.exit(1)
