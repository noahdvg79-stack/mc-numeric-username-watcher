import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://discord.com/api/v10"
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = os.environ["SOURCE_CHANNEL_ID"]
OUTPUT_WEBHOOK_URL = os.environ["OUTPUT_WEBHOOK_URL"]
STATE_FILE = "state.json"

# Scan the latest 250 messages each run. Discord allows at most 100 per request.
MESSAGES_TO_SCAN = 250
PAGE_SIZE = 100

# Matches messages such as: "Minecraft username found: _816"
USERNAME_LINE = re.compile(
    r"minecraft username found:\s*([0-9_]{3,16})",
    re.IGNORECASE,
)

def request_json(url, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"User-Agent": "MCNumericUsernameWatcher/1.1"}
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
        # Valid: 1862, _816, 6_79. Invalid: letters, trailing underscore,
        # multiple underscores, or names outside the 3-16 character range.
        if not 3 <= len(name) <= 16:
            continue
        if not re.fullmatch(r"(?:[0-9]+(?:_[0-9]+)?|_[0-9]+)", name):
            continue
        if not any(ch.isdigit() for ch in name):
            continue
        if name.count("_") > 1 or "__" in name:
            continue
        names.append(name)
    return names

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            raise ValueError("state.json must contain a JSON object")
        state.setdefault("last_message_id", "0")
        state.setdefault("seen_names", [])
        return state
    except FileNotFoundError:
        return {"last_message_id": "0", "seen_names": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        f.write("\n")

def fetch_latest_messages(headers, count=MESSAGES_TO_SCAN):
    """Fetch up to `count` newest messages using Discord's 100-message page limit."""
    collected = []
    before_id = None

    while len(collected) < count:
        page_size = min(PAGE_SIZE, count - len(collected))
        params = {"limit": page_size}
        if before_id is not None:
            params["before"] = before_id
        url = f"{API}/channels/{CHANNEL_ID}/messages?{urllib.parse.urlencode(params)}"
        page = request_json(url, headers=headers)

        if not isinstance(page, list):
            raise RuntimeError("Unexpected response while reading channel messages.")
        if not page:
            break

        collected.extend(page)
        # Discord returns newest first; use the oldest item as the next page cursor.
        before_id = min(page, key=lambda m: int(m["id"]))["id"]

        if len(page) < page_size:
            break

    # Deduplicate defensively, then process old-to-new.
    unique_by_id = {str(message["id"]): message for message in collected}
    messages = list(unique_by_id.values())
    messages.sort(key=lambda m: int(m["id"]))
    return messages[-count:]

def send_to_webhook(names, message_links):
    unique = list(dict.fromkeys(names))
    if not unique:
        return

    # Keep messages under Discord's 2000-character content limit.
    # Split into multiple webhook posts if a batch is unusually large.
    source_links = list(dict.fromkeys(message_links))[:5]
    lines = ["**Numeric-only Minecraft usernames found**"]
    lines.extend(f"`{name}`" for name in unique)
    if source_links:
        lines.extend(["", "Source messages: " + " ".join(source_links)])

    content = "\n".join(lines)
    if len(content) <= 1900:
        request_json(OUTPUT_WEBHOOK_URL, method="POST", payload={"content": content})
        return

    batch = []
    current_length = len("**Numeric-only Minecraft usernames found**\n")
    for name in unique:
        line = f"`{name}`\n"
        if batch and current_length + len(line) > 1700:
            request_json(
                OUTPUT_WEBHOOK_URL,
                method="POST",
                payload={"content": "**Numeric-only Minecraft usernames found**\n" + "\n".join(f"`{n}`" for n in batch)},
            )
            batch = []
            current_length = len("**Numeric-only Minecraft usernames found**\n")
        batch.append(name)
        current_length += len(line)
    if batch:
        request_json(
            OUTPUT_WEBHOOK_URL,
            method="POST",
            payload={"content": "**Numeric-only Minecraft usernames found**\n" + "\n".join(f"`{n}`" for n in batch)},
        )

def main():
    state = load_state()
    seen_names = set(state.get("seen_names", []))
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}

    # Every run re-reads the latest 250 messages, not just messages newer than a cursor.
    messages = fetch_latest_messages(headers, MESSAGES_TO_SCAN)
    found = []
    links = []

    for message in messages:
        fresh = []
        for name in extract_numeric_names(message):
            if name not in seen_names:
                fresh.append(name)
                seen_names.add(name)
        if fresh:
            found.extend(fresh)
            if message.get("guild_id"):
                links.append(
                    f"https://discord.com/channels/{message['guild_id']}/{CHANNEL_ID}/{message['id']}"
                )

    if found:
        send_to_webhook(found, links)
        print("Sent usernames:", ", ".join(dict.fromkeys(found)))
    else:
        print(f"No unseen numeric-only usernames found in the latest {len(messages)} messages.")

    if messages:
        state["last_message_id"] = str(max(int(m["id"]) for m in messages))
    # Keep a bounded history so state.json does not grow indefinitely.
    state["seen_names"] = sorted(seen_names)[-10000:]
    save_state(state)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
