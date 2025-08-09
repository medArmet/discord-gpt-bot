# gpt_discord_bot.py
import os
import aiohttp  # used to download non-image files
import discord
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MODEL = "gpt-5"  # or "gpt-5-mini"

client_openai = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.content.startswith("!gpt"):
        return

    prompt = message.content[5:].strip()
    attachments = message.attachments

    if not prompt and not attachments:
        await message.channel.send("❗ Please provide text or attach a file/image.")
        return

    thinking_msg = await message.channel.send("⏳ Thinking...")

    try:
        content_parts = []

        # user text
        if prompt:
            content_parts.append({"type": "input_text", "text": prompt})

        # attachments
        for a in attachments:
            ctype = (a.content_type or "").lower()
            if ctype.startswith("image/"):
                content_parts.append({"type": "input_image", "image_url": a.url})
            else:
                # download file and try utf-8 decode (safe-ish)
                async with aiohttp.ClientSession() as session:
                    async with session.get(a.url) as resp:
                        file_bytes = await resp.read()

                try:
                    text = file_bytes.decode("utf-8", errors="ignore")
                    # keep it reasonable to avoid token blowups
                    if len(text) > 50_000:
                        text = text[:50_000] + "\n...[truncated]..."
                    content_parts.append({
                        "type": "input_text",
                        "text": f"File '{a.filename}' content:\n{text}"
                    })
                except Exception:
                    content_parts.append({
                        "type": "input_text",
                        "text": f"File '{a.filename}' uploaded, but could not decode as text."
                    })

        # call GPT-5
        response = client_openai.responses.create(
            model=MODEL,
            input=[{"role": "user", "content": content_parts}],
            max_output_tokens=1500,
        )

        reply = (response.output_text or "").strip() or "⚠️ I couldn't generate a response."
        await thinking_msg.edit(content=reply[:1900])  # Discord limit ~2000

    except Exception as e:
        await thinking_msg.edit(content=f"❌ Error: {e}")

client.run(DISCORD_TOKEN)
