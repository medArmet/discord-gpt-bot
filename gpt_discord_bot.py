import os
import io
import csv
import asyncio
import aiohttp
import discord
from openai import OpenAI

# ===== CONFIG =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PRIMARY_MODEL = "gpt-5"       # main model
FALLBACK_MODEL = "gpt-5-mini" # fallback if empty output

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is not set")

client_openai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== HELPERS =====
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

def extract_text(completion) -> str:
    try:
        msg = completion.choices[0].message
        if msg and getattr(msg, "content", None):
            return msg.content.strip()
    except Exception:
        pass
    return ""

async def call_openai_chat(model: str, messages: list, max_tokens: int = 1200):
    """Run blocking API call in a thread (prevents Discord heartbeat stalls)."""
    def _do():
        return client_openai.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,  # GPT-5 requires this name
        )
    return await asyncio.to_thread(_do)

# ===== DISCORD EVENTS =====
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.content.startswith("!gpt"):
        return

    raw_prompt = message.content[5:]  # keep raw for logging
    prompt = raw_prompt.strip()
    attachments = message.attachments or []

    if not prompt and not attachments:
        await message.channel.send("❗ Please provide text or attach a file/image.")
        return

    thinking = await message.channel.send("⏳ Thinking...")

    try:
        # --- Build user content ---
        text_only = True
        content_blocks = []  # used when we have attachments (images/files)

        if attachments:
            text_only = False

        if text_only:
            # SIMPLE STRING for text-only (most reliable path)
            user_message_content = prompt or "Please answer in plain text."
        else:
            # MULTIMODAL ARRAY for images/files
            if prompt:
                content_blocks.append({"type": "text", "text": prompt})

            for a in attachments:
                ctype = (a.content_type or "").lower()
                if ctype.startswith("image/"):
                    content_blocks.append({"type": "image_url", "image_url": {"url": a.url}})
                else:
                    # Non-image file: download & include text/preview
                    file_bytes = await download_bytes(a.url)

                    if ctype.endswith("/csv") or a.filename.lower().endswith(".csv"):
                        preview = csv_preview(file_bytes, limit_rows=30)
                        content_blocks.append({
                            "type": "text",
                            "text": (
                                f"CSV file '{a.filename}' preview (first ~30 rows):\n\n{preview}\n\n"
                                "Task: Analyze this CSV. Summarize columns & datatypes, key stats, outliers, "
                                "sentiment themes (if any), and give 3 actionable insights."
                            )
                        })
                    else:
                        # generic text decode (truncate to keep tokens reasonable)
                        try:
                            txt = file_bytes.decode("utf-8", errors="ignore")
                        except Exception:
                            txt = ""
                        if txt.strip():
                            if len(txt) > 50_000:
                                txt = txt[:50_000] + "\n...[truncated]..."
                            content_blocks.append({
                                "type": "text",
                                "text": f"File '{a.filename}' content:\n{txt}\n\nTask: Analyze this file."
                            })
                        else:
                            content_blocks.append({
                                "type": "text",
                                "text": (
                                    f"File '{a.filename}' uploaded (type: {ctype or 'unknown'}), "
                                    "but could not be decoded as text. Suggest how to process it."
                                )
                            })

            if not prompt:
                content_blocks.append({
                    "type": "text",
                    "text": "Please respond only in plain text with a concise but detailed analysis."
                })

            user_message_content = content_blocks

        # --- Build messages ---
        system_prompt = (
            "You are a helpful assistant. Always respond in plain text. "
            "Be concise, use bullet points when helpful, and give clear next steps."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message_content},
        ]

        # --- LOG what we're sending (for Render logs) ---
        print("DEBUG OpenAI call → model:", PRIMARY_MODEL)
        if text_only:
            print("DEBUG user content (text):", (user_message_content[:400] + "…") if len(user_message_content) > 400 else user_message_content)
        else:
            # Don’t print entire files; just the block types and first 120 chars of texts
            brief = []
            for b in content_blocks:
                if b.get("type") == "image_url":
                    brief.append({"type": "image_url", "url": b["image_url"].get("url", "")})
                else:
                    t = b.get("text", "")
                    brief.append({"type": "text", "text": (t[:120] + "…") if len(t) > 120 else t})
            print("DEBUG user content (blocks):", brief)

        # --- Primary call ---
        completion = await call_openai_chat(PRIMARY_MODEL, messages, max_tokens=1200)
        reply = extract_text(completion)

        # --- Fallback if empty ---
        if not reply:
            print("DEBUG: Empty reply from primary model. Retrying with simplified text message and fallback model.")
            # Retry with string-only message to remove any chance of schema quirks.
            retry_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt or "Please answer in plain text."},
            ]
            # Try primary again
            completion = await call_openai_chat(PRIMARY_MODEL, retry_messages, max_tokens=800)
            reply = extract_text(completion)

            if not reply:
                # Try fallback model
                completion = await call_openai_chat(FALLBACK_MODEL, retry_messages, max_tokens=800)
                reply = extract_text(completion)

        if not reply:
            reply = "⚠️ I couldn't generate a response."

        await thinking.edit(content=reply[:1900])  # Discord limit ~2000 chars

    except Exception as e:
        await thinking.edit(content=f"❌ Error: {e}")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
