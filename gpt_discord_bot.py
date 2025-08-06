import discord
import openai
import os

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
        user_prompt = message.content[5:].strip()
        image_urls = [attachment.url for attachment in message.attachments if attachment.content_type and attachment.content_type.startswith("image/")]

        if not user_prompt and not image_urls:
            await message.channel.send("❗ Please provide text or attach an image.")
            return

        await message.channel.send("⏳ Analyzing...")

        # Construct messages for GPT-4o
        messages = [
            {"role": "user", "content": []}
        ]

        if user_prompt:
            messages[0]["content"].append({"type": "text", "text": user_prompt})

        for url in image_urls:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": url}
            })

        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1000
            )
            reply = response.choices[0].message.content.strip()
            await message.channel.send(reply[:1900])
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)