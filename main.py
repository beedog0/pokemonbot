import discord
from discord.ext import commands
from google import genai
import os
import requests
import random
from io import BytesIO
from centering import analyze_centering

# 1. Setup Bot Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 2. Setup Gemini Client (Using the new GenAI SDK)
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

<<<<<<< HEAD
# Store last graded image and card name per channel
last_graded = {}
=======
# Data Storage
last_graded = {}  # {channel_id: {"url": attachment_url, "card": card_name}}
ask_history = {}  # {user_id: [history]}
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68

<<<<<<< HEAD
# Store conversation history per user for !ask context
ask_history = {}

=======
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68
@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Professional is active! Geometric Scanning Enabled.')

# --- SHARED GRADE FUNCTION (UPGRADED WITH GEOMETRIC ANALYSIS) ---
async def run_grade(ctx, status_msg, img_data, img_url, override_card=None):
    # Run OpenCV centering analysis BEFORE calling Gemini
    centering_result = analyze_centering(img_data)
    centering_block = centering_result["prompt_injection"]

    if centering_result["success"]:
        await status_msg.edit(content="📐 Centering measured — now grading with Gemini...")

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

<<<<<<< HEAD
    {centering_block}

    PSA GRADING STANDARDS — CENTERING:
    - PSA 10 allows up to 60/40 centering on the front and 75/25 on the back.
    - PSA 9 allows slightly looser centering but must still be reasonably centered.
    - If computed centering measurements are provided above, USE THEM as the primary data for your centering assessment.
    - Only override the measurements if the image clearly shows they are wrong (e.g., card was at extreme angle).
    - Only dock the grade for centering if it clearly exceeds these tolerances.
    - Do NOT recite the PSA tolerance numbers in the centering assessment.
=======
    STEP 4: Market Value (Use Google Search)
    - Find current SOLD prices for Raw, PSA 9, and PSA 10.
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68

    FORMAT THE RESPONSE EXACTLY LIKE THIS:

    # [PREDICTED PSA GRADE]
    ## [CARD NAME] - [SET] - [NUMBER]
    **Rarity:** [rarity]

    💵 **Market Value**
    ┣ Raw — $X.XX (source)
    ┣ PSA 9 — $X.XX (source)
    ┗ PSA 10 — $X.XX (source)

    ━━━━━━━━━━━━━━━━━━━━━━
<<<<<<< HEAD
    📐 **Centering** {"(Measured: LR " + centering_result['ratios']['lr'] + ", TB " + centering_result['ratios']['tb'] + ")" if centering_result['success'] else "(Visual estimate)"}
    [Brief assessment of border symmetry — reference measured ratios if available]
=======
    📐 **Geometric Centering Analysis**
    ┣ **L/R Ratio:** [Calculated Ratio, e.g., 62/38]
    ┣ **T/B Ratio:** [Calculated Ratio, e.g., 55/45]
    ┗ **Status:** [e.g. "Left-Heavy" or "Top-Heavy"]
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68

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

<<<<<<< HEAD
        footers = ["Official MUKSCAN PSA Estimate", "Verified Market Data", "MUKSCAN: The Gold Standard"]

        footer_text = random.choice(footers)
        if centering_result["success"]:
            r = centering_result["ratios"]
            footer_text += f" | 📐 LR {r['lr']} TB {r['tb']}"

        embed = discord.Embed(title="📋 MUKSCAN Professional Report", color=0xFFD700)
=======
        embed = discord.Embed(title="📋 MUKSCAN Geometric Grading Report", color=0xFFD700)
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68
        embed.set_thumbnail(url=img_url)
        embed.description = response.text
<<<<<<< HEAD
        embed.set_footer(text=footer_text)
=======
        embed.set_footer(text="Verified via Geometric Centering Analysis")
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68

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
<<<<<<< HEAD
async def price(ctx, *, card_name: str = None):
    if not card_name:
        await ctx.send("❓ Please provide a card name! Example: `!price Charizard Base Set 4/102`")
        return

    status_msg = await ctx.send(f"💸 Searching full market data for **{card_name}**...")

    try:
        price_prompt = f"""
        Find the most complete and current market pricing for the Pokémon card: {card_name}.

        PRICING RULES — follow this source priority for EVERY grade:
        1. Primary: eBay most recent completed/sold listing. Label as (eBay sold MM/DD/YYYY).
        2. Fallback 1: TCGPlayer Market Price. Label as (TCGPlayer).
        3. Fallback 2: PriceCharting.com — ONLY use results explicitly labeled "PSA [grade]". Generic "Grade 7/8/9" labels are NOT PSA — ignore them. Label as (PriceCharting).
        - For PSA 1-5 with no real data anywhere, estimate based on price curve and label as (~est.).
        - Do NOT use active auction bids or unsold listings.
        - If a language tag is included (JP, KR, etc.), search that version specifically.

        FORMAT EXACTLY LIKE THIS:

        ## [CARD NAME] - Price Report

        💵 **Raw**
        ┗ Last Sold: $X.XX (eBay sold MM/DD/YYYY)

        📊 **Graded Prices**
        ┣ PSA 1  — $X.XX (source)
        ┣ PSA 2  — $X.XX (source)
        ┣ PSA 3  — $X.XX (source)
        ┣ PSA 4  — $X.XX (source)
        ┣ PSA 5  — $X.XX (source)
        ┣ PSA 6  — $X.XX (source)
        ┣ PSA 7  — $X.XX (source)
        ┣ PSA 8  — $X.XX (source)
        ┣ PSA 9  — $X.XX (source)
        ┗ PSA 10 — $X.XX (source)

        STRICT RULES:
        - List ALL grades. Do not skip any.
        - Always include source in parentheses.
        - Never use generic PriceCharting grade labels — PSA-specific only.
        - No citations, no footnotes, no code blocks, no markdown tables.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=price_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        embed = discord.Embed(title=f"💰 Full Price Report: {card_name}", color=0x2ecc71)
        embed.description = response.text
        embed.set_footer(text="eBay sold → TCGPlayer → PriceCharting (PSA only) | MUKSCAN")

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Price Check Error: {str(e)}")


# --- HELPER: Extract card name from context ---
async def resolve_card_name(ctx, card_name):
    if card_name:
        return card_name

    if ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if ref.embeds:
            desc = ref.embeds[0].description or ""
            for line in desc.split('\n'):
                if line.startswith('##'):
                    return line.replace('##', '').strip()

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

        STEP 1: Use Google Search — source priority:
        1. eBay completed/sold average. Label as (eBay sold).
        2. TCGPlayer Market Price. Label as (TCGPlayer).
        3. PriceCharting — PSA-labeled data only, no generic grades. Label as (PriceCharting).
        - No active bids or unsold listings.
        - Use language-specific pricing if card has a language tag.

        STEP 2: Calculate using PSA Economy = $25/card.
        - 60% chance PSA 9, 20% PSA 10, 20% PSA 8 or lower.

        STEP 3: FLIP or NO FLIP verdict.

        FORMAT EXACTLY LIKE THIS:

        ## [CARD NAME]

        💵 **Prices**
        ┣ Raw — $X.XX (source)
        ┣ PSA 9 — $X.XX (source)
        ┗ PSA 10 — $X.XX (source)

        ━━━━━━━━━━━━━━━━━━━━━━
        📊 **Profit Breakdown**
        ┣ Expected return after fees — $X.XX
        ┗ Net profit vs raw — $X.XX

        ━━━━━━━━━━━━━━━━━━━━━━
        **✅ VERDICT: FLIP** or **❌ VERDICT: NO FLIP**
        [1-sentence reason]

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


# --- COMMAND: !invest ---
@bot.command()
async def invest(ctx, *, card_name: str = None):
    resolved = await resolve_card_name(ctx, card_name)

    if not resolved:
        await ctx.send("❓ Please provide a card name.\nExample: `!invest Mew ex Shiny Treasure ex 347/190`")
        return

    status_msg = await ctx.send(f"📈 Running investment analysis on **{resolved}**...")

    try:
        invest_prompt = f"""
        You are a Pokémon TCG investment analyst. Perform a full investment analysis on:
        Card: {resolved}

        Use Google Search to research ALL of the following:

        STEP 1 — CURRENT PRICING (sold listings only, no active bids):
        - Raw current price (eBay sold or TCGPlayer)
        - PSA 9 and PSA 10 current price (TCGPlayer primary, eBay sold fallback)

        STEP 2 — PRICE HISTORY & TREND:
        - Search PriceCharting for this card's price history
        - What was the price 6 months ago, 1 year ago, 2 years ago (approximate)?
        - Is the trend: Rising / Falling / Stable / Volatile?
        - What caused major price movements if known?

        STEP 3 — PRINT RUN STATUS:
        - Is this set still in print or out of print?
        - Has it been reprinted or is a reprint announced?
        - Search "[card set name] reprint" and "[card set name] out of print" to confirm
        - How does print status affect supply and price outlook?

        STEP 4 — RECENT NEWS:
        - Search "[card name] price news 2025 2026" for any relevant developments
        - Any tournament usage, competitive relevance, or hype driving price?
        - Any Pokémon anime, game, or media tie-ins boosting demand?
        - Any sealed product affecting raw supply?

        STEP 5 — INVESTMENT SCORING:
        Rate each of the following on a scale of 1-10 and explain briefly:
        - Demand Score: How sought after is this card?
        - Scarcity Score: How rare/limited is supply?
        - Stability Score: How stable has the price been?
        - Growth Score: How likely is price appreciation?

        STEP 6 — OVERALL VERDICT

        FORMAT EXACTLY LIKE THIS — put the summary at the top, details below:

        ## [CARD NAME] — Investment Report

        ⚡ **QUICK SUMMARY**
        ┣ Overall Rating: [BUY / HOLD / AVOID]
        ┣ Risk Level: [Low / Medium / High]
        ┣ Success Rate: [X]% (estimated probability of value increase in 12 months)
        ┣ 12-Month Outlook: [Bullish 📈 / Neutral ➡️ / Bearish 📉]
        ┗ Best Strategy: [e.g. "Buy raw, hold 12 months" or "Grade and hold PSA 10"]

        ━━━━━━━━━━━━━━━━━━━━━━
        💵 **Current Prices**
        ┣ Raw — $X.XX (source)
        ┣ PSA 9 — $X.XX (source)
        ┗ PSA 10 — $X.XX (source)

        ━━━━━━━━━━━━━━━━━━━━━━
        📉 **Price History**
        ┣ 2 Years Ago — ~$X.XX
        ┣ 1 Year Ago — ~$X.XX
        ┣ 6 Months Ago — ~$X.XX
        ┣ Today — $X.XX
        ┗ Trend: [Rising / Falling / Stable / Volatile]

        ━━━━━━━━━━━━━━━━━━━━━━
        🖨️ **Print Run Status**
        ┣ Status: [In Print / Out of Print / Reprint Announced]
        ┣ Set: [set name]
        ┗ Impact: [1 sentence on how print status affects price]

        ━━━━━━━━━━━━━━━━━━━━━━
        📰 **Recent News**
        [2-4 bullet points of relevant news affecting this card's value]

        ━━━━━━━━━━━━━━━━━━━━━━
        🎯 **Investment Scores**
        ┣ Demand     — [X]/10 — [brief reason]
        ┣ Scarcity   — [X]/10 — [brief reason]
        ┣ Stability  — [X]/10 — [brief reason]
        ┗ Growth     — [X]/10 — [brief reason]

        ━━━━━━━━━━━━━━━━━━━━━━
        📊 **Full Analysis**
        [2-3 sentences summarizing the overall investment case for this card]

        🔗 **Price Chart:** https://www.pricecharting.com/search-products?q=[CARD+NAME+URL+ENCODED]&type=prices

        STRICT RULES:
        - Put the Quick Summary at the TOP always.
        - Only use sold pricing — no active bids.
        - No citations, no footnotes, no code blocks.
        - Replace spaces with + in the PriceCharting URL.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=invest_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        reply = response.text
        chunks = [reply[i:i+4000] for i in range(0, len(reply), 4000)]

        await status_msg.delete()

        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title=f"📈 Investment Report: {resolved}" if i == 0 else f"📈 Investment Report: {resolved} (continued)",
                description=chunk,
                color=0xf39c12
            )
            if i == len(chunks) - 1:
                embed.set_footer(text="MUKSCAN Investment Analysis | Not financial advice")
            await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Investment Analysis Error: {str(e)}")


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
        You are a Pokémon card grading analyst. Look up the PSA population report for:
        Card: {resolved}

        Use Google Search to find current PSA population data.

        FORMAT EXACTLY LIKE THIS:

        ## [CARD NAME] — PSA Population Report

        👥 **Total Graded:** [number]

        📊 **Grade Breakdown**
        ┣ PSA 10 — [number]
        ┣ PSA 9  — [number]
        ┣ PSA 8  — [number]
        ┣ PSA 7  — [number]
        ┗ PSA 6 and below — [number]

        ━━━━━━━━━━━━━━━━━━━━━━
        📈 **Analysis**
        PSA 10 Rate: [X]% of all graded copies
        [1-2 sentences on what the pop report means for value and rarity]

        STRICT RULES: No citations, no footnotes, no code blocks, no markdown tables.
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


# --- COMMAND: !ask ---
@bot.command()
async def ask(ctx, *, question: str = None):
    user_id = ctx.author.id

    if not question:
        if ctx.message.reference:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if ref.embeds and ref.embeds[0].description:
                question = f"Based on this info: {ref.embeds[0].description[:500]}"
            elif ref.content:
                question = ref.content
        if not question:
            await ctx.send("❓ Ask me something! Example: `!ask any TCG stores near 77001`")
            return

    elif ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if ref.embeds and ref.embeds[0].description:
            question = f"Regarding this: {ref.embeds[0].description[:300]}\n\nMy question: {question}"
        elif ref.content and ref.author.bot:
            question = f"Regarding your previous response: {ref.content[:300]}\n\nMy question: {question}"

    if user_id not in ask_history:
        ask_history[user_id] = []

    if len(ask_history[user_id]) > 20:
        ask_history[user_id] = ask_history[user_id][-20:]

    ask_history[user_id].append({
        "role": "user",
        "parts": [{"text": question}]
    })

=======
async def ask(ctx, *, question: str):
>>>>>>> 0f039237e18ac24e2b5e3ca8a4e6b2c1625f1e68
    status_msg = await ctx.send("🔍 MUKSCAN is looking into that...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"You are MUKSCAN, a TCG expert. Question: {question}",
        config=genai.types.GenerateContentConfig(tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())])
    )
    await status_msg.edit(content=response.text)

bot.run(os.getenv('DISCORD_TOKEN'))
