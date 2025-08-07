import os
import discord
from openai import OpenAI
import aiohttp

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
    image_attachments = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]

    if not prompt and not image_attachments:
        await message.channel.send("❗ Please provide a prompt or attach an image.")
        return

    await message.channel.send("⏳ Thinking...")

    try:
        # Prepare multimodal input
        content = []
        if prompt:
            content.append({"type": "text", "text": prompt})

        for img in image_attachments:
            content.append({"type": "image_url", "image_url": {"url": img.url}})

        response = client_openai.responses.create(
            model="gpt-4o",
            input=content,
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