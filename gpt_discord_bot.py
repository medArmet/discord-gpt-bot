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
    if message.author.bot:
        return

    if message.content.startswith("!gpt"):
        prompt = message.content[5:].strip()

        if not prompt:
            await message.channel.send("❗ Please provide a prompt to search, analyze, or respond to.")
            return

        await message.channel.send("⏳ Thinking...")

        try:
            response = client_openai.responses.create(
                model="gpt-4o",
                input=prompt,
                tools=[
                    {"type": "web_search"},
                    {"type": "file_search"},
                    {"type": "image_generation"}
                ]
            )
            await message.channel.send(response.output_text[:1900])
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)