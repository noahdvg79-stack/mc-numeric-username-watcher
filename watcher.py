import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://discord.com/api/v10"
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = os.environ["SOURCE_CHANNEL_ID"]
OUTPUT_WEBHOOK_URL = os.environ["OUTPUT_WEBHOOK_URL"]
STATE_FILE = "state.json"

# Matches the username in messages like: "🎉 Minecraft username found: _816"
USERNAME_LINE = re.compile(
    r"minecraft username found:\s*([0-9_]{3,16})",
    re.IGNORECASE
)

def request_json(url, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"User-Agent": "MCNumericUsernameWatcher/1.0"}
    if headers:
        req_headers.update(headers)
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord API returned HTTP {e.code}: {body[:500]}") from e

def get_message_text(message):
    chunks = [message.get("content", "")]
    for embed in message.get("embeds", []):
        chunks.append(embed.get("title", ""))
        chunks.append(embed.get("description", ""))
        for field in embed.get("fields", []):
            chunks.append(field.get("name", ""))
            chunks.append(field.get("value", ""))
    return "\n".join(chunks)

def extract_numeric_names(message):
    text = get_message_text(message)
    names = []
    for match in USERNAME_LINE.finditer(text):
        name = match.group(1)
        # Only digits, optionally one underscore. Must contain at least one digit.
        if len(name) < 3 or len(name) > 16:
            continue
        if not re.fullmatch(r"(?=.*[0-9])[0-9]+(?:_[0-9]+)?|_[0-9]+", name):
            continue
        if "__" in name or name.count("_") > 1:
            continue
        names.append(name)
    return names

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_message_id": "0", "seen_names": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")

def send_to_webhook(names, message_links):
    # Keep each Discord webhook message comfortably under Discord's content limit.
    unique = list(dict.fromkeys(names))
    if not unique:
        return
    lines = ["**Numeric-only Minecraft usernames found**"]
    lines.extend(f"`{name}`" for name in unique)
    if message_links:
        lines.append("")
        lines.append("Source messages: " + " ".join(message_links[:5]))
    content = "\n".join(lines)
    if len(content) > 1900:
        content = content[:1850] + "\n…(truncated)"
    request_json(OUTPUT_WEBHOOK_URL, method="POST", payload={"content": content})

def main():
    state = load_state()
    last_id = int(state.get("last_message_id", "0"))
    seen_names = set(state.get("seen_names", []))

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    url = f"{API}/channels/{CHANNEL_ID}/messages?limit=100"
    messages = request_json(url, headers=headers)
    if not isinstance(messages, list):
        raise RuntimeError("Unexpected response while reading channel messages.")

    # Discord returns newest first; process old-to-new.
    messages.sort(key=lambda m: int(m["id"]))
    new_messages = [m for m in messages if int(m["id"]) > last_id]

    found = []
    links = []
    newest_id = last_id
    for message in new_messages:
        newest_id = max(newest_id, int(message["id"]))
        names = extract_numeric_names(message)
        fresh = [name for name in names if name not in seen_names]
        if fresh:
            found.extend(fresh)
            seen_names.update(fresh)
            links.append(f"https://discord.com/channels/{message['guild_id']}/{CHANNEL_ID}/{message['id']}")

    if found:
        send_to_webhook(found, links)
        print("Sent usernames:", ", ".join(dict.fromkeys(found)))
    else:
        print("No new numeric-only usernames found.")

    # Advance the cursor even when there are no matching names.
    if messages:
        newest_in_batch = max(int(m["id"]) for m in messages)
        newest_id = max(newest_id, newest_in_batch)
    state["last_message_id"] = str(newest_id)
    state["seen_names"] = sorted(seen_names)[-5000:]
    save_state(state)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
