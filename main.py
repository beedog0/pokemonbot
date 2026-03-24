import discord
from discord.ext import commands
from google import genai
import os
import requests
import random
from io import BytesIO

# 1. Setup Bot Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 2. Setup Gemini Client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Professional is active!')

# --- COMMAND: !grade ---
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
        await ctx.send("📸 No photo found! Attach a card or reply to one with `!grade`.")
        return

    status_msg = await ctx.send("🧐 MUKSCAN is performing a professional Grade & Price analysis...")

    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()

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

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')],
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]  # ← fixed
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

# --- COMMAND: !price ---
@bot.command()
async def price(ctx, *, card_name: str = None):
    target_query = card_name
    if not target_query and ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if ref.embeds:
            target_query = ref.embeds[0].description.split('\n')[1]

    if not target_query:
        await ctx.send("❓ Please provide a card name! Example: `!price Charizard Base Set 4/102` or reply to a grade report.")
        return

    status_msg = await ctx.send(f"💸 Searching market data for **{target_query}**...")

    try:
        price_prompt = f"Find the current market price for the Pokémon card: {target_query}. Provide the average 'Sold' price on eBay and the current 'Market Price' on TCGPlayer for Raw, PSA 9, and PSA 10 conditions. Keep it brief."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=price_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]  # ← fixed
            )
        )

        embed = discord.Embed(title=f"💰 Market Value: {target_query}", color=0x2ecc71)
        embed.description = response.text
        embed.set_footer(text="Live data from eBay & TCGPlayer via Google Search")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Price Check Error: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))