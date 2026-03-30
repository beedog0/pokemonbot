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

# 2. Setup Gemini Client (Using the new GenAI SDK)
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Data Storage
last_graded = {}  # {channel_id: {"url": attachment_url, "card": card_name}}
ask_history = {}  # {user_id: [history]}

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Professional is active! Geometric Scanning Enabled.')

# --- SHARED GRADE FUNCTION (UPGRADED WITH GEOMETRIC ANALYSIS) ---
async def run_grade(ctx, status_msg, img_data, img_url, override_card=None):
    if override_card:
        card_instruction = f"The card is confirmed to be: {override_card}. Use this as ground truth."
    else:
        card_instruction = """STEP 1: Identify the card: Name, Set, Number, and Rarity.
        Detect language from Name/Attack text ONLY (ignore art script)."""

    prompt = f"""
    You are a professional PSA grader. Perform a GEOMETRIC CENTERING ANALYSIS on this card.

    {card_instruction}

    STEP 2: GEOMETRIC ANALYSIS
    1. Identify the 'Outer Edge' of the card and the 'Inner Art Frame' (where the holo/art meets the border).
    2. Measure the thickness of the four borders (Left, Right, Top, Bottom) in normalized pixels.
    3. Calculate the Centering Ratios:
       - Left/Right: (Left / (Left + Right)) * 100
       - Top/Bottom: (Top / (Top + Bottom)) * 100

    STEP 3: PSA GRADING RULES
    - PSA 10: Front centering must be 60/40 or better.
    - PSA 9: Front centering must be 65/35 or better.
    - PSA 8: Front centering allows up to 70/30.
    - Mathematically compensate for perspective/tilt in the photo.

    STEP 4: Market Value (Use Google Search)
    - Find current SOLD prices for Raw, PSA 9, and PSA 10.

    FORMAT THE RESPONSE EXACTLY LIKE THIS:

    # [PREDICTED PSA GRADE]
    ## [CARD NAME] - [SET] - [NUMBER]
    **Rarity:** [rarity]

    💵 **Market Value**
    ┣ Raw — $X.XX (source)
    ┣ PSA 9 — $X.XX (source)
    ┗ PSA 10 — $X.XX (source)

    ━━━━━━━━━━━━━━━━━━━━━━
    📐 **Geometric Centering Analysis**
    ┣ **L/R Ratio:** [Calculated Ratio, e.g., 62/38]
    ┣ **T/B Ratio:** [Calculated Ratio, e.g., 55/45]
    ┗ **Status:** [e.g. "Left-Heavy" or "Top-Heavy"]

    💥 **Physical Condition**
    - Corners: [Assessment]
    - Edges: [Assessment]
    - Surface: [Assessment]

    📝 **Rationale**
    [1 sentence explaining why the centering ratio/condition led to this specific grade]
    """

    try:
        # Using gemini-2.5-flash for high-precision spatial reasoning
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')],
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        card_name = None
        for line in response.text.split('\n'):
            if line.startswith('##'):
                card_name = line.replace('##', '').strip()
                break

        last_graded[ctx.channel.id] = {"url": img_url, "card": card_name or override_card}

        embed = discord.Embed(title="📋 MUKSCAN Geometric Grading Report", color=0xFFD700)
        embed.set_thumbnail(url=img_url)
        embed.description = response.text
        embed.set_footer(text="Verified via Geometric Centering Analysis")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")

# --- COMMANDS ---

@bot.command()
async def grade(ctx):
    attachment = ctx.message.attachments[0] if ctx.message.attachments else None
    if not attachment and ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        attachment = ref.attachments[0] if ref.attachments else None

    if not attachment:
        return await ctx.send("📸 No photo found! Attach a card or reply to one.")

    status_msg = await ctx.send("🧐 MUKSCAN is performing Geometric Scanning...")
    img_data = requests.get(attachment.url).content
    await run_grade(ctx, status_msg, img_data, attachment.url)

@bot.command()
async def price(ctx, *, card_name: str):
    status_msg = await ctx.send(f"💸 Searching market data for **{card_name}**...")
    prompt = f"Find sold prices (eBay/TCGPlayer) for: {card_name}. List Raw, PSA 9, and PSA 10."
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=genai.types.GenerateContentConfig(tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())])
    )
    await status_msg.edit(content=response.text)

@bot.command()
async def ask(ctx, *, question: str):
    status_msg = await ctx.send("🔍 MUKSCAN is looking into that...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"You are MUKSCAN, a TCG expert. Question: {question}",
        config=genai.types.GenerateContentConfig(tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())])
    )
    await status_msg.edit(content=response.text)

bot.run(os.getenv('DISCORD_TOKEN'))