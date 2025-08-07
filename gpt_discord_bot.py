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
            await message.channel.send("❗ Please provide a prompt to search or ask.")
            return

        await message.channel.send("⏳ Searching the web...")

        try:
            response = client_openai.responses.create(
                model="gpt-4o",  # ✅ DO NOT use gpt-4o-search-preview here
                tools=[{"type": "web_search"}],  # ✅ Not web_search_preview
                input=prompt
            )
            await message.channel.send(response.output_text[:1900])
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)