# Minecraft numeric username watcher (GitHub Actions)

This project runs on GitHub-hosted runners, not on your PC. It checks the source Discord channel approximately every five minutes and forwards new matching usernames to your destination Discord webhook.

## What it scans

Each run reads the **latest 250 messages** in the source channel. Discord allows at most 100 messages per API request, so the script fetches multiple pages.

It searches message content and common embed text fields for the phrase:

`Minecraft username found: _816`

It accepts 3–16 character names containing only digits and at most one underscore, with at least one digit. Examples accepted: `1862`, `_816`, `6_79`. Names with letters, two underscores, or a trailing underscore are ignored.

The script remembers usernames already forwarded in `state.json`, so the same username is not repeatedly posted on every run. It checks the latest 250 messages every time, but it only forwards names it has not seen before.

## Setup

1. Create a Discord application/bot at https://discord.com/developers/applications.
2. Invite the bot to the source server with `View Channels` and `Read Message History`.
3. In Discord, enable Developer Mode under User Settings → Advanced, then right-click the source channel and choose Copy Channel ID.
4. Create a webhook in the destination channel under Edit Channel → Integrations → Webhooks.
5. Create a GitHub repository and upload `watcher.py`, `state.json`, `README.md`, and `.github/workflows/watch.yml`, preserving the folder structure.
6. Under repository Settings → Secrets and variables → Actions, add:
   - `DISCORD_BOT_TOKEN` — bot token
   - `SOURCE_CHANNEL_ID` — source channel ID
   - `OUTPUT_WEBHOOK_URL` — destination webhook URL
7. In Actions, enable workflows if prompted, then run **Watch Minecraft usernames** manually to test.

## Important limitations

- GitHub's scheduled workflow is approximate and can be delayed; this is not instant monitoring.
- The first run scans the latest 250 messages. Later runs also scan the latest 250 messages, but forward only usernames not already recorded.
- The source messages must contain the phrase `Minecraft username found:` followed by the username.
- GitHub Actions commits `state.json` to remember names already forwarded.
- Do not put your bot token or webhook URL in code or commit them to the repository. Use GitHub Actions secrets only.
- Never use a personal Discord account token or self-bot.
