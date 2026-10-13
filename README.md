# Minecraft numeric username watcher (GitHub Actions)

This project runs in GitHub Actions, not on your PC. It checks a Discord channel every five minutes and sends matching names to a Discord webhook you control.

It looks for messages containing a line such as:

`🎉 Minecraft username found: _816`

Accepted names are 3–16 characters and contain only digits plus at most one underscore, with at least one digit. Names with letters or `__` are ignored. It checks message content and common embed text fields.

## Setup

### 1. Create a Discord bot for reading the source channel
1. Go to https://discord.com/developers/applications and create an application.
2. Open **Bot** and create/reset its bot token. Keep the token private.
3. Under **OAuth2 → URL Generator**, select the `bot` scope and the `View Channels` and `Read Message History` permissions.
4. Use the generated invite URL to add the bot to the server where the username finder posts.
5. Copy the source channel ID: in Discord, enable **User Settings → Advanced → Developer Mode**, then right-click the channel and choose **Copy Channel ID**.

The bot needs permission to view that channel and read its message history. Do not use a personal account token or self-bot.

### 2. Create a destination Discord webhook
In the channel where you want notifications, open **Edit Channel → Integrations → Webhooks → New Webhook**, then copy its webhook URL. Treat that URL like a password.

### 3. Put the files in a GitHub repository
1. Create a new repository on https://github.com/new.
2. Upload `watcher.py`, `state.json`, and the `.github/workflows/watch.yml` file, preserving the folder structure.
3. In the repository, open **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `DISCORD_BOT_TOKEN` — the bot token
   - `SOURCE_CHANNEL_ID` — the ID of the channel to read
   - `OUTPUT_WEBHOOK_URL` — the destination webhook URL
4. Open the **Actions** tab and enable workflows if GitHub prompts you.
5. Choose **Watch Minecraft usernames → Run workflow** to test it.

The first run checks up to the latest 100 channel messages. Later runs process messages newer than the saved cursor. GitHub scheduled jobs are approximate and may run late; they are not a real-time listener.

## Notes and troubleshooting
- The bot must be invited to the source server and have permission to view the channel and read message history.
- This expects the phrase `Minecraft username found:` in the message or embed text.
- GitHub Actions commits `state.json` to remember the last processed message and avoid repeatedly scanning old messages.
- If you want to reset the scan, edit `state.json` and set `last_message_id` to `"0"` (the first run then checks only the latest 100 messages).
- Never commit tokens or webhook URLs into the code. Use GitHub repository secrets only.
