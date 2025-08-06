import discord
import openai
import os

# ✅ Use OpenAI v1+ SDK correctly
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
            await message.channel.send("❗ Please provide a prompt.")
            return

        await message.channel.send("⏳ Generating...")

        try:
            response = openai_client.chat.completions.create(
                model="o1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=500
            )
            reply = response.choices[0].message.content.strip()
            await message.channel.send(reply[:1900])
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)