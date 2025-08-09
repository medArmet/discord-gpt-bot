import aiohttp
import io
import discord
from openai import OpenAI

client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@client.event
async def on_message(message):
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

        # Add text from user
        if prompt:
            content_parts.append({"type": "input_text", "text": prompt})

        # Process attachments
        for a in attachments:
            if a.content_type and a.content_type.startswith("image/"):
                # Vision input
                content_parts.append({"type": "input_image", "image_url": a.url})
            else:
                # Download file from Discord
                async with aiohttp.ClientSession() as session:
                    async with session.get(a.url) as resp:
                        file_bytes = await resp.read()
                # Basic handling: treat as text if possible
                try:
                    text = file_bytes.decode("utf-8", errors="ignore")
                    content_parts.append({"type": "input_text", "text": f"File '{a.filename}' content:\n{text}"})
                except:
                    content_parts.append({"type": "input_text", "text": f"File '{a.filename}' uploaded, but could not decode as text."})

        # Send to GPT-5
        response = client_openai.responses.create(
            model="gpt-5",
            input=[{"role": "user", "content": content_parts}],
            max_output_tokens=1500
        )

        reply = response.output_text.strip()
        await thinking_msg.edit(content=reply[:1900])

    except Exception as e:
        await thinking_msg.edit(content=f"❌ Error: {e}")
