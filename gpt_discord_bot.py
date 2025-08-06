import discord
import openai
import os

# ✅ Get credentials securely from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ✅ Enable message content intent
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
            await message.channel.send("❗ Please provide a prompt.")
            return

        await message.channel.send("⏳ Generating...")

        try:
            response = openai.ChatCompletion.create(
                model="o1-pro",  # 💰 Most expensive OpenAI model
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=500,
            )
            reply = response.choices[0].message.content.strip()
            await message.channel.send(reply[:1900])  # Discord message limit
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)