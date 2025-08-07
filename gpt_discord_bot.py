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
    attachments = [a for a in message.attachments if a.content_type and a.content_type.startswith("image/")]

    if not prompt and not attachments:
        await message.channel.send("❗ Please provide a prompt or attach an image.")
        return

    await message.channel.send("⏳ Thinking...")

    try:
        # 🔍 Case 1: Image analysis — use chat.completions (vision support)
        if attachments:
            content = [{"type": "text", "text": prompt or "Analyze this image."}]
            for a in attachments:
                content.append({"type": "image_url", "image_url": {"url": a.url}})

            response = client_openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=1000
            )
            reply = response.choices[0].message.content.strip()

        # 🔍 Case 2: Pure text prompt — use responses.create with tools
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