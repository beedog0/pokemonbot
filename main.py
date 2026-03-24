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

# Store last graded image and card name per channel
last_graded = {}  # {channel_id: {"url": attachment_url, "card": card_name}}

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
        name="📊 !flip [card name]",
        value="Check if a card is worth grading. Can reply to a grade report or photo, or type a name.\n`!flip Pikachu 018/091 Paldean Fates`",
        inline=False
    )
    embed.add_field(
        name="👥 !pop <card name>",
        value="Check the PSA population report for a card — how many graded at each grade.\n`!pop Mew ex Shiny Treasure ex 347/190`",
        inline=False
    )
    embed.set_footer(text="MUKSCAN: The Gold Standard")
    await ctx.send(embed=embed)


# --- SHARED GRADE FUNCTION ---
async def run_grade(ctx, status_msg, img_data, img_url, override_card=None):
    if override_card:
        card_instruction = f"The card is confirmed to be: {override_card}. Do NOT attempt to re-identify it — use this as ground truth."
    else:
        card_instruction = "STEP 1: Identify the card in extreme detail: Name, Set, Number, and Rarity (e.g., SIR, Full Art, Illustration Rare, Holo, Reverse Holo). Detect the language of the card. If it is NOT English, label it clearly (e.g., JP, KR, DE, FR, ES, IT, PT). If it is English, do not add any language label."

    prompt = f"""
    You are a professional PSA grader and market analyst.

    {card_instruction}
    STEP 2: Use Google Search to find the CURRENT market price for this specific version (Raw, PSA 9, and PSA 10).
    Only use SOLD listings — completed eBay sales or TCGPlayer Market Price.
    Do NOT use active auction bids, active listings, or Buy It Now prices that have not sold.
    If sold data is unavailable, use TCGPlayer Market Price from TCGPlayer.com.
    If the card is a non-English version, search for prices specific to that language version (e.g., JP, KR).
    STEP 3: Grade the physical card in the image (Centering, Corners, Edges, Surface).

    FORMAT THE RESPONSE EXACTLY LIKE THIS:

    # [PREDICTED PSA GRADE]
    ## [CARD NAME] - [SET] - [NUMBER] [JP] (only add language tag if non-English)
    **Rarity:** [e.g. Special Illustration Rare / Holo / etc]
    **Language:** [e.g. Japanese / Korean / German — omit this line entirely if English]
    **Market Value:** [Live Price for Raw, PSA 9, and PSA 10 — SOLD listings only]

    ---
    **📐 Centering Assessment**
    (Brief assessment)

    **💥 Physical Condition**
    (Details on Corners, Edges, and Surface)

    **📝 Rationale**
    (1-sentence explaining the grade)

    IMAGING NOTES:
    - If the card is inside a sleeve or toploader, ignore the sleeve edges when judging borders.
    - If there is glare or reflections on the card, do NOT interpret bright spots as surface damage.
    - Compensate for lighting artifacts when assessing centering — judge borders conservatively.
    - Camera angle can distort border appearance; account for perspective when measuring centering.
    - When in doubt on centering due to image quality, lean toward a more favorable assessment.

    STRICT RULES:
    - Put the Grade and Price at the TOP.
    - Identify rarity markers like SIR, FA, SAR, etc.
    - Only use SOLD pricing — no active auctions, no unsold listings.
    - DO NOT use JSON, brackets, or code blocks.
    - DO NOT use footnotes or citations.
    - For PSA 10 candidates, note if centering could not be confirmed due to image quality.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')],
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        # Extract card name from response for context storage
        card_name = None
        lines = response.text.split('\n')
        for line in lines:
            if line.startswith('##'):
                card_name = line.replace('##', '').strip()
                break

        last_graded[ctx.channel.id] = {"url": img_url, "card": card_name or override_card}

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

    last_graded[ctx.channel.id] = {"url": attachment.url, "card": None}
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

    cached = last_graded.get(ctx.channel.id)
    if not cached:
        await ctx.send("❓ No recent card found in this channel. Run `!grade` first.")
        return

    img_url = cached["url"]
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
        - Average recent SOLD price on eBay (Raw) — completed sales only, no active listings
        - Current Market Price on TCGPlayer (Raw)
        - PSA 9 average SOLD price — completed sales only
        - PSA 10 average SOLD price — completed sales only

        Do NOT use active auction bids or unsold listings under any circumstances.
        If sold data is unavailable, fall back to TCGPlayer Market Price.
        If the card name includes a language (e.g. JP, KR), search for that specific language version's pricing.

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
        embed.set_footer(text="Sold listings only | eBay & TCGPlayer via Google Search")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Price Check Error: {str(e)}")


# --- HELPER: Extract card name from context ---
async def resolve_card_name(ctx, card_name):
    """Try to get card name from: typed input → replied embed → last graded cache"""
    if card_name:
        return card_name

    # Check if replying to a MUKSCAN grade report embed
    if ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if ref.embeds:
            desc = ref.embeds[0].description or ""
            for line in desc.split('\n'):
                if line.startswith('##'):
                    return line.replace('##', '').strip()

    # Fall back to last graded cache
    cached = last_graded.get(ctx.channel.id)
    if cached and cached.get("card"):
        return cached["card"]

    return None


# --- COMMAND: !flip ---
@bot.command()
async def flip(ctx, *, card_name: str = None):
    resolved = await resolve_card_name(ctx, card_name)

    if not resolved:
        await ctx.send("❓ Please provide a card name, or reply to a grade report / photo.\nExample: `!flip Pikachu 018/091 Paldean Fates`")
        return

    status_msg = await ctx.send(f"📊 Calculating flip potential for **{resolved}**...")

    try:
        flip_prompt = f"""
        You are a Pokémon card investment analyst. Evaluate whether this card is worth grading and flipping:
        Card: {resolved}

        STEP 1: Use Google Search to find current SOLD prices only:
        - Raw average SOLD price (eBay completed sales or TCGPlayer Market Price)
        - PSA 9 average SOLD price (completed eBay sales only)
        - PSA 10 average SOLD price (completed eBay sales only)
        Do NOT use active auction bids or unsold listings under any circumstances.
        If the card includes a language tag (e.g. JP, KR), search for that language version's pricing specifically.

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

        embed = discord.Embed(title=f"📊 Flip Analysis: {resolved}", color=0x9b59b6)
        embed.description = response.text
        embed.set_footer(text="MUKSCAN Flip Calculator | PSA Economy $25/card | Sold listings only")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Flip Analysis Error: {str(e)}")


# --- COMMAND: !pop ---
@bot.command()
async def pop(ctx, *, card_name: str = None):
    resolved = await resolve_card_name(ctx, card_name)

    if not resolved:
        await ctx.send("❓ Please provide a card name, or reply to a grade report.\nExample: `!pop Mew ex Shiny Treasure ex 347/190`")
        return

    status_msg = await ctx.send(f"👥 Pulling PSA population data for **{resolved}**...")

    try:
        pop_prompt = f"""
        You are a Pokémon card grading analyst. Look up the PSA population report for this card:
        Card: {resolved}

        Use Google Search to find the current PSA population data.

        FORMAT EXACTLY LIKE THIS:

        ## [CARD NAME] - PSA Population Report
        **Total Graded:** [number]

        | Grade | Population |
        |-------|------------|
        | PSA 10 | [number] |
        | PSA 9  | [number] |
        | PSA 8  | [number] |
        | PSA 7  | [number] |
        | PSA 6 and below | [number] |

        ---
        **📊 Analysis**
        PSA 10 Rate: [X]% of all graded copies
        (1-2 sentences on what the pop report means for this card's value and rarity)

        STRICT RULES: No citations, no footnotes, no code blocks outside the table.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=pop_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        embed = discord.Embed(title=f"👥 PSA Pop Report: {resolved}", color=0xe74c3c)
        embed.description = response.text
        embed.set_footer(text="Population data via PSA | MUKSCAN")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Pop Report Error: {str(e)}")


bot.run(os.getenv('DISCORD_TOKEN'))