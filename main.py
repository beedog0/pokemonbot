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

# 2. Setup Gemini Client
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

    # Download image
    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()
    except Exception:
        await status_msg.edit(content="❌ Failed to download the image.")
        return

    prompt = """
    You are a professional PSA grader and market analyst.
    
    STEP 1: Identify the card in extreme detail: Name, Set, Number, and Rarity (e.g., SIR, Full Art, Illustration Rare, Holo, Reverse Holo).
    STEP 2: Use Google Search to find the CURRENT market price for this specific version (Raw, PSA 9, and PSA 10).
    STEP 3: Grade the physical card in the image (Centering, Corners, Edges, Surface).
    
    FORMAT THE RESPONSE EXACTLY LIKE THIS:
    
    # [PREDICTED PSA GRADE]
    ## [CARD NAME] - [SET] - [NUMBER]
    **Rarity:** [e.g. Special Illustration Rare / Holo / etc]
    **Market Value:** [Live Price for Raw, PSA 9, and PSA 10]
    
    ---
    **📐 Centering Assessment**
    (Brief assessment)
    
    **💥 Physical Condition**
    (Details on Corners, Edges, and Surface)
    
    **📝 Rationale**
    (1-sentence explaining the grade)
    
    STRICT RULES:
    - Put the Grade and Price at the TOP.
    - Identify rarity markers like SIR, FA, SAR, etc.
    - DO NOT use JSON, brackets, or code blocks.
    - DO NOT use footnotes or citations.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-lite',  # ← fixed model
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')],
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]  # ← fixed tool
            )
        )

        footers = ["Official MUKSCAN PSA Estimate", "Verified Market Data", "MUKSCAN: The Gold Standard"]

        embed = discord.Embed(title="📋 MUKSCAN Professional Report", color=0xFFD700)
        embed.set_thumbnail(url=attachment.url)
        embed.description = response.text
        embed.set_footer(text=random.choice(footers))

        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))