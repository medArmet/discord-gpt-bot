import os
import discord
from openai import OpenAI

client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.content.startswith("!gpt"):
        return

    prompt = message.content[5:].strip()
    attachments = message.attachments or []
    image_attachments = [a for a in attachments if a.content_type and a.content_type.startswith("image/")]

    if not prompt and not image_attachments:
        await message.channel.send("❗ Please provide a message or attach an image.")
        return

    await message.channel.send("⏳ Thinking...")

    try:
        # ✅ Case 1: Handle images only if present
        if image_attachments:
            content = [{"type": "text", "text": prompt or "Analyze this image."}]
            for a in image_attachments:
                content.append({"type": "image_url", "image_url": {"url": a.url}})

            response = client_openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=1000
            )
            reply = response.choices[0].message.content.strip()

        # ✅ Case 2: Only text → use .responses.create() to avoid gpt-image-1
        else:
            response = client_openai.responses.create(
                model="gpt-4o",
                input=prompt,
                tools=[
                    {"type": "web_search"},
                    {"type": "image_generation"}
                ]
            )
            reply = response.output_text.strip()

        await message.channel.send(reply[:1900])

    except Exception as e:
        await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)