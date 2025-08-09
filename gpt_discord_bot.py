# gpt_discord_bot.py
import os
import io
import csv
import asyncio
import aiohttp
import discord
from openai import OpenAI

# ========= Config =========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MODEL = "gpt-5"  # or "gpt-5-mini"

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is not set")

client_openai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ========= Helpers =========
async def download_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.read()

def csv_preview(data: bytes, limit_rows: int = 30) -> str:
    """Return a small CSV preview (handles UTF-8 + latin-1; strips BOM)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="ignore")
    if text and text[0] == "\ufeff":
        text = text[1:]

    buf = io.StringIO(text)
    reader = csv.reader(buf)
    rows = []
    for i, row in enumerate(reader):
        if i >= limit_rows:
            rows.append(["...[truncated rows]..."])
            break
        rows.append(row)

    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue()

def build_user_content(prompt: str, attachments: list[discord.Attachment]):
    """
    Build Chat Completions 'content' list: mix of text blocks and image_url blocks.
    """
    content: list[dict] = []
    if prompt:
        content.append({"type": "text", "text": prompt})

    for a in attachments:
        ctype = (a.content_type or "").lower()
        if ctype.startswith("image/"):
            content.append({"type": "image_url", "image_url": {"url": a.url}})
        else:
            # non-image: try to read and include preview/text
            # (Do NOT block event loop here—handled outside)
            pass  # we’ll append after we download in on_message

    return content

# ========= Discord Events =========
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
        # Build mixed content (text + any image URLs)
        user_content = build_user_content(prompt, attachments)

        # Download non-image attachments and append as text
        for a in attachments:
            ctype = (a.content_type or "").lower()
            if ctype.startswith("image/"):
                continue

            file_bytes = await download_bytes(a.url)
            if ctype.endswith("/csv") or a.filename.lower().endswith(".csv"):
                preview = csv_preview(file_bytes, limit_rows=30)
                user_content.append({
                    "type": "text",
                    "text": (
                        f"CSV file '{a.filename}' preview (first ~30 rows):\n\n{preview}\n\n"
                        "Task: Analyze this CSV. Summarize columns & datatypes, key stats, outliers, "
                        "sentiment themes (if any), and give 3 actionable insights."
                    )
                })
            else:
                # generic text decode with truncation
                try:
                    txt = file_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    txt = ""
                if txt.strip():
                    if len(txt) > 50_000:
                        txt = txt[:50_000] + "\n...[truncated]..."
                    user_content.append({
                        "type": "text",
                        "text": f"File '{a.filename}' content:\n{txt}\n\nTask: Analyze this file."
                    })
                else:
                    user_content.append({
                        "type": "text",
                        "text": (
                            f"File '{a.filename}' uploaded (type: {ctype or 'unknown'}), "
                            "but it couldn't be decoded as text. Suggest how to process it."
                        )
                    })

        # If user only sent files, ensure we ask for plain text output
        if not prompt:
            user_content.append({
                "type": "text",
                "text": "Please respond only in plain text with a concise but detailed analysis."
            })

        # Prepare Chat Completions payload
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful analyst. Always respond in plain text. "
                    "Be concise but include bullet points and short rationale where helpful."
                ),
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

        # Blocking API call -> run in a worker thread
        def call_openai_chat():
            return client_openai.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=1200,
                temperature=0.2,
            )

        completion = await asyncio.to_thread(call_openai_chat)
        reply = (completion.choices[0].message.content or "").strip() or \
                "⚠️ I couldn't generate a response."

        await thinking.edit(content=reply[:1900])  # Discord limit ~2000

    except Exception as e:
        await thinking.edit(content=f"❌ Error: {e}")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
