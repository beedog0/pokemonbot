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

# Store last graded image per channel
last_graded = {}  # {channel_id: attachment_url}

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Professional is active!')


# --- COMMAND: !commands ---
@bot.command(name='commands')
async def command_list(ctx):
    embed = discord.Embed(
        title="🤖 MUKSCAN Command List",
        description="Your professional Pokémon card grading assistant.",
        color=0xFFD700
    )
    embed.add_field(
        name="📸 !grade",
        value="Attach a card photo to get a PSA grade estimate + market value.\n`!grade` (with attachment)",
        inline=False
    )
    embed.add_field(
        name="🔄 !regrade <card name>",
        value="Correct the card identity and re-run the analysis on the last graded image.\n`!regrade Pikachu 018/091 Paldean Fates`",
        inline=False
    )
    embed.add_field(
        name="💰 !price <card name>",
        value="Look up live market prices from eBay & TCGPlayer.\n`!price Charizard Base Set 4/102`",
        inline=False
    )
    embed.add_field(
        name="📊 !flip <card name>",
        value="Check if a card is worth grading — shows raw vs PSA 9/10 price spread and estimated profit after PSA fees.\n`!flip Pikachu 018/091 Paldean Fates`",
        inline=False
    )
    embed.set_footer(text="MUKSCAN: The Gold Standard")
    await ctx.send(embed=embed)


# --- SHARED GRADE FUNCTION ---
async def run_grade(ctx, status_msg, img_data, img_url, override_card=None):
    if override_card:
        card_instruction = f"The card is confirmed to be: {override_card}. Do NOT attempt to re-identify it — use this as ground truth."
    else:
        card_instruction = "STEP 1: Identify the card in extreme detail: Name, Set, Number, and Rarity (e.g., SIR, Full Art, Illustration Rare, Holo, Reverse Holo)."

    prompt = f"""
    You are a professional PSA grader and market analyst.

    {card_instruction}
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
            model='gemini-2.5-flash',
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')],
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        footers = ["Official MUKSCAN PSA Estimate", "Verified Market Data", "MUKSCAN: The Gold Standard"]

        embed = discord.Embed(title="📋 MUKSCAN Professional Report", color=0xFFD700)
        embed.set_thumbnail(url=img_url)
        embed.description = response.text
        embed.set_footer(text=random.choice(footers))

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")


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

    last_graded[ctx.channel.id] = attachment.url
    status_msg = await ctx.send("🧐 MUKSCAN is performing a professional Grade & Price analysis...")

    try:
        img_response = requests.get(attachment.url)
        img_data = BytesIO(img_response.content).read()
        await run_grade(ctx, status_msg, img_data, attachment.url)
    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")


# --- COMMAND: !regrade ---
@bot.command()
async def regrade(ctx, *, correction: str = None):
    if not correction:
        await ctx.send("❓ Tell me the correct card! Example: `!regrade Pikachu 018/091 Paldean Fates`")
        return

    img_url = last_graded.get(ctx.channel.id)
    if not img_url:
        await ctx.send("❓ No recent card found in this channel. Run `!grade` first.")
        return

    status_msg = await ctx.send(f"🔄 Re-grading as **{correction}**...")

    try:
        img_response = requests.get(img_url)
        img_data = BytesIO(img_response.content).read()
        await run_grade(ctx, status_msg, img_data, img_url, override_card=correction)
    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")


# --- COMMAND: !price ---
@bot.command()
async def price(ctx, *, card_name: str = None):
    if not card_name:
        await ctx.send("❓ Please provide a card name! Example: `!price Charizard Base Set 4/102`")
        return

    status_msg = await ctx.send(f"💸 Searching market data for **{card_name}**...")

    try:
        price_prompt = f"""
        Find the current market price for the Pokémon card: {card_name}.
        
        Provide:
        - Average recent sold price on eBay (Raw)
        - Current Market Price on TCGPlayer (Raw)
        - PSA 9 sold price
        - PSA 10 sold price
        
        Keep it brief and clean. No citations, no footnotes, no code blocks.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=price_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        embed = discord.Embed(title=f"💰 Market Value: {card_name}", color=0x2ecc71)
        embed.description = response.text
        embed.set_footer(text="Live data via Google Search | eBay & TCGPlayer")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Price Check Error: {str(e)}")


# --- COMMAND: !flip ---
@bot.command()
async def flip(ctx, *, card_name: str = None):
    if not card_name:
        await ctx.send("❓ Please provide a card name! Example: `!flip Pikachu 018/091 Paldean Fates`")
        return

    status_msg = await ctx.send(f"📊 Calculating flip potential for **{card_name}**...")

    try:
        flip_prompt = f"""
        You are a Pokémon card investment analyst. Evaluate whether this card is worth grading and flipping:
        Card: {card_name}

        STEP 1: Use Google Search to find current prices:
        - Raw average sold price (eBay)
        - PSA 9 average sold price
        - PSA 10 average sold price

        STEP 2: Calculate profit potential using these fixed PSA grading costs:
        - PSA Economy submission: $25 per card
        - Assume 60% chance of PSA 9, 20% chance of PSA 10, 20% chance of PSA 8 or lower

        STEP 3: Give a clear FLIP / NO FLIP verdict.

        FORMAT EXACTLY LIKE THIS:

        ## [CARD NAME]
        **Raw Price:** $X.XX
        **PSA 9 Value:** $X.XX | **PSA 10 Value:** $X.XX

        ---
        **📊 Profit Breakdown**
        Expected return after fees: $X.XX
        Net profit vs raw: $X.XX

        **✅ VERDICT: FLIP** or **❌ VERDICT: NO FLIP**
        (1-sentence reason)

        STRICT RULES: No JSON, no code blocks, no citations, no footnotes.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=flip_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        embed = discord.Embed(title=f"📊 Flip Analysis: {card_name}", color=0x9b59b6)
        embed.description = response.text
        embed.set_footer(text="MUKSCAN Flip Calculator | PSA Economy $25/card")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Flip Analysis Error: {str(e)}")


bot.run(os.getenv('DISCORD_TOKEN'))