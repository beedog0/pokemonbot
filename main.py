import discord
from discord.ext import commands
from google import genai
import os
import requests
import random
from io import BytesIO

# 1. Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 2. Setup Client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Professional is active!')

@bot.command()
async def grade(ctx):
    attachment = None
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
    elif ctx.message.reference:
        referenced_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if referenced_msg.attachments:
            attachment = referenced_msg.attachments[0]

    if not attachment:
        await ctx.send("📸 No photo found! Attach a card or reply to one.")
        return

    status_msg = await ctx.send("🧐 MUKSCAN is performing a professional Grade & Price analysis...")

    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()

        # UPDATED PROMPT: Specific "Top-Heavy" template
        prompt = """
        You are a professional PSA grader and market analyst.
        First, identify the card in detail: Name, Set, Number, and Rarity (e.g., SIR, FA, SAR, Holo).
        Then, use Google Search to find current market prices.
        
        YOU MUST FOLLOW THIS LAYOUT EXACTLY:
        
        # [PREDICTED PSA GRADE]
        ## [ESTIMATED PRICE: Raw: $X | PSA 9: $X | PSA 10: $X]
        ### [CARD NAME] - [SET] - [NUMBER] ([RARITY])
        
        ---
        **📐 Centering**
        (Brief assessment)
        
        **💥 Physical Condition**
        (Details on Corners, Edges, and Surface)
        
        **📝 Rationale**
        (1-sentence explanation)
        
        STRICT RULES:
        - The Grade and Price MUST be the first two lines.
        - Use the specific rarity acronyms like SIR, FA, etc.
        - NO JSON, NO brackets, NO citations.
        """

        response = client.models.generate_content(
            model='gemini-2.0-flash-lite-preview', 
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')],
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearchRetrieval())]
            )
        )
        
        embed = discord.Embed(title="📋 MUKSCAN Professional Report", color=0xFFD700)
        embed.set_thumbnail(url=attachment.url)
        embed.description = response.text
        embed.set_footer(text="Official MUKSCAN PSA Estimate • Verified Market Data")
        
        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))