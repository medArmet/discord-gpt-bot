import discord
import openai
import os
import httpx
import json

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Tool function: Basic web search mock using DuckDuckGo
def web_search(query: str) -> str:
    url = f"https://html.duckduckgo.com/html/?q={query}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            if "result__title" in response.text:
                return f"🔍 Top result for '{query}' found via DuckDuckGo (mock response)."
            else:
                return f"No strong result found for '{query}'."
    except Exception as e:
        return f"❌ Web search failed: {str(e)}"

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!gpt"):
        user_prompt = message.content[5:].strip()
        image_urls = [a.url for a in message.attachments if a.content_type and a.content_type.startswith("image/")]

        if not user_prompt and not image_urls:
            await message.channel.send("❗ Please provide text or an image.")
            return

        await message.channel.send("⏳ Analyzing...")

        tools = [{
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for recent information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        }]

        # Build the initial messages
        messages = [{"role": "user", "content": []}]
        if user_prompt:
            messages[0]["content"].append({"type": "text", "text": user_prompt})
        for url in image_urls:
            messages[0]["content"].append({"type": "image_url", "image_url": {"url": url}})

        try:
            # First GPT call using gpt-4o-search-preview
            response = openai_client.chat.completions.create(
                model="gpt-4o-search-preview",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=1000
            )

            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                for tool_call in tool_calls:
                    if tool_call.function.name == "web_search":
                        args = json.loads(tool_call.function.arguments)
                        result = web_search(args["query"])
                        messages.append(response.choices[0].message)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result
                        })
                        # Second GPT call with result
                        followup = openai_client.chat.completions.create(
                            model="gpt-4o-search-preview",
                            messages=messages,
                            max_tokens=1000
                        )
                        reply = followup.choices[0].message.content.strip()
                        await message.channel.send(reply[:1900])
                        return

            reply = response.choices[0].message.content.strip()
            await message.channel.send(reply[:1900])

        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")

client.run(DISCORD_TOKEN)