# gpt_discord_bot.py
import os
import io
import csv
import asyncio
import aiohttp
import discord
from openai import OpenAI

# --- config ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MODEL = "gpt-5"  # or "gpt-5-mini"

# fail fast if missing env vars
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is not set")

client_openai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def _extract_output_text(resp) -> str:
    """
    Robustly extract text from Responses API results.
    """
    # 1) Best case: output_text property
    text = getattr(resp, "output_text", None)
    if text:
        return text.strip()

    # 2) Fallback: walk through output[] blocks
    try:
        blocks = getattr(resp, "output", []) or []
        parts = []
        for blk in blocks:
            for c in getattr(blk, "content", []) or []:
                if getattr(c, "type", "") in ("output_text", "text") and getattr(c, "text", None):
                    parts.append(c.text)
        if parts:
            return "\n".join(parts).strip()
    except Exception:
        pass

    return ""

async def _download_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()

def _csv_preview(data: bytes, limit_rows: int = 30) -> str:
    """
    Decode CSV (utf-8/latin-1 fallback) and return up to N rows as CSV again.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="ignore")

    buf = io.StringIO(text)
    reader = csv.reader(buf)
    rows = []
    for i, row in enumerate(reader):
        if i >= limit_rows:
            rows.append(["...[truncated rows]..."])
            break
        rows.append(row)

    # Re-serialize preview to CSV
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(rows)
    return out.getvalue()

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.content.startswith("!gpt"):
        return

    prompt = message.content[5:].strip()
    attachments = message.attachments or []

    if not prompt and not attachments:
        await message.channel.send("❗ Please provide text or attach a file/image.")
        return

    thinking = await message.channel.send("⏳ Thinking...")

    try:
        content = []
        if prompt:
            content.append({"type": "input_text", "text": prompt})

        # Handle attachments
        for a in attachments:
            ctype = (a.content_type or "").lower()
            if ctype.startswith("image/"):
                # Vision input via URL
                content.append({"type": "input_image", "image_url": a.url})
            else:
                # Download non-image file
                file_bytes = await _download_bytes(a.url)

                if ctype.endswith("/csv") or a.filename.lower().endswith(".csv"):
                    preview = _csv_preview(file_bytes, limit_rows=30)
                    content.append({
                        "type": "input_text",
                        "text": f"CSV file '{a.filename}' preview (first ~30 rows):\n\n{preview}\n\nPlease analyze this CSV."
                    })
                else:
                    # Generic text decode with truncation
                    try:
                        text = file_bytes.decode("utf-8", errors="ignore")
                    except Exception:
                        text = ""

                    if text.strip():
                        if len(text) > 50_000:
                            text = text[:50_000] + "\n...[truncated]..."
                        content.append({
                            "type": "input_text",
                            "text": f"File '{a.filename}' content:\n{text}"
                        })
                    else:
                        content.append({
                            "type": "input_text",
                            "text": f"File '{a.filename}' uploaded (type: {ctype or 'unknown'}), "
                                    f"but it isn't readable as text. Please advise how to process."
                        })

        # Run the blocking OpenAI call in a thread so we don't freeze the event loop
        def _call_openai():
            return client_openai.responses.create(
                model=MODEL,
                input=[{"role": "user", "content": content}],
                max_output_tokens=1500,
            )

        resp = await asyncio.to_thread(_call_openai)
        reply = _extract_output_text(resp) or "⚠️ I couldn't generate a response."

        # Discord limit ~2000 chars
        await thinking.edit(content=reply[:1900])

    except Exception as e:
        await thinking.edit(content=f"❌ Error: {e}")

if __name__ == "__main__":
    # -u for unbuffered logs on Render is set via startCommand (recommended)
    client.run(DISCORD_TOKEN)
