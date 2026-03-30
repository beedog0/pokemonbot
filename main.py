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

# 2. Setup Gemini Client
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

# Store last graded image and card name per channel
last_graded = {}

# Store conversation history per user for !ask context
ask_history = {}

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
        value="Full price breakdown Raw through PSA 10 with sources.\n`!price Charizard Base Set 4/102`",
        inline=False
    )
    embed.add_field(
        name="📊 !flip [card name]",
        value="Check if a card is worth grading. Can reply to a grade report or photo, or type a name.\n`!flip Pikachu 018/091 Paldean Fates`",
        inline=False
    )
    embed.add_field(
        name="📈 !invest <card name>",
        value="Full investment analysis — risk, outlook, print run status, price history & trends.\n`!invest Mew ex Shiny Treasure ex 347/190`",
        inline=False
    )
    embed.add_field(
        name="👥 !pop <card name>",
        value="Check the PSA population report for a card — how many graded at each grade.\n`!pop Mew ex Shiny Treasure ex 347/190`",
        inline=False
    )
    embed.add_field(
        name="❓ !ask <question>",
        value="Ask anything Pokémon or TCG related — events, stores, new sets, conventions, and more.\n`!ask any TCG stores near 77001`",
        inline=False
    )
    embed.add_field(
        name="🗑️ !clearchat",
        value="Clear your !ask conversation history and start fresh.\n`!clearchat`",
        inline=False
    )
    embed.set_footer(text="MUKSCAN: The Gold Standard")
    await ctx.send(embed=embed)


# --- SHARED GRADE FUNCTION ---
async def run_grade(ctx, status_msg, img_data, img_url, override_card=None):
    # Run OpenCV centering analysis BEFORE calling Gemini
    centering_result = analyze_centering(img_data)
    centering_block = centering_result["prompt_injection"]

    if centering_result["success"]:
        await status_msg.edit(content="📐 Centering measured — now grading with Gemini...")

    if override_card:
        card_instruction = f"The card is confirmed to be: {override_card}. Do NOT attempt to re-identify it — use this as ground truth."
    else:
        card_instruction = """STEP 1: Identify the card in extreme detail: Name, Set, Number, and Rarity (e.g., SIR, Full Art, Illustration Rare, Holo, Reverse Holo).

    LANGUAGE DETECTION RULES — READ CAREFULLY:
    - Determine the card's language by reading the CARD NAME at the top, the ATTACK NAMES, and the ATTACK/ABILITY DESCRIPTIONS only.
    - DO NOT use artwork, background text, flavor text embedded in the illustration, or decorative kanji/script in the art to determine language.
    - If the card name, attack names, and descriptions are in English, the card is English — even if the artwork contains Japanese or other script.
    - Only label the card as non-English (JP, KR, DE, FR, etc.) if the printed card name and attack text are in that language.
    - If non-English, add the language tag to the card header (e.g., [JP]) and include a Language line in the output."""

    prompt = f"""
    You are a professional PSA grader and market analyst.

    {card_instruction}

    STEP 2: Use Google Search to find the CURRENT market price for this specific version (Raw, PSA 9, and PSA 10).
    PRICING RULES:
    - For Raw price: use eBay completed/sold listings average. Label as (eBay sold).
    - For PSA 9 and PSA 10: ALWAYS use TCGPlayer Market Price as the primary source. Label as (TCGPlayer).
    - If TCGPlayer data is unavailable, use eBay completed sales and label as (eBay sold).
    - If eBay is also unavailable, use PriceCharting.com but ONLY results explicitly labeled as PSA grades. Label as (PriceCharting).
    - Do NOT use active auction bids, active listings, or unsold Buy It Now prices ever.
    - If the card is a confirmed non-English version, search for prices specific to that language version.

    STEP 3: Grade the physical card in the image (Centering, Corners, Edges, Surface).

    {centering_block}

    PSA GRADING STANDARDS — CENTERING:
    - PSA 10 allows up to 60/40 centering on the front and 75/25 on the back.
    - PSA 9 allows slightly looser centering but must still be reasonably centered.
    - If computed centering measurements are provided above, USE THEM as the primary data for your centering assessment.
    - Only override the measurements if the image clearly shows they are wrong (e.g., card was at extreme angle).
    - Only dock the grade for centering if it clearly exceeds these tolerances.
    - Do NOT recite the PSA tolerance numbers in the centering assessment.

    FORMAT THE RESPONSE EXACTLY LIKE THIS — use this exact structure, no deviations:

    # [PREDICTED PSA GRADE]
    ## [CARD NAME] - [SET] - [NUMBER] [LANGUAGE TAG if non-English]
    **Rarity:** [rarity]
    **Language:** [language — omit line entirely if English]

    💵 **Market Value**
    ┣ Raw — $X.XX (source)
    ┣ PSA 9 — $X.XX (source)
    ┗ PSA 10 — $X.XX (source)

    ━━━━━━━━━━━━━━━━━━━━━━
    📐 **Centering** {"(Measured: LR " + centering_result['ratios']['lr'] + ", TB " + centering_result['ratios']['tb'] + ")" if centering_result['success'] else "(Visual estimate)"}
    [Brief assessment of border symmetry — reference measured ratios if available]

    💥 **Physical Condition**
    [Corners / Edges / Surface — each on its own line if needed]

    📝 **Rationale**
    [1 sentence explaining the grade]

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
    - Always include the price source in parentheses next to each price.
    - DO NOT recite PSA tolerance numbers anywhere in the response.
    - DO NOT use JSON, code blocks, or markdown tables.
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

        card_name = None
        lines = response.text.split('\n')
        for line in lines:
            if line.startswith('##'):
                card_name = line.replace('##', '').strip()
                break

        last_graded[ctx.channel.id] = {"url": img_url, "card": card_name or override_card}

        footers = ["Official MUKSCAN PSA Estimate", "Verified Market Data", "MUKSCAN: The Gold Standard"]

        footer_text = random.choice(footers)
        if centering_result["success"]:
            r = centering_result["ratios"]
            footer_text += f" | 📐 LR {r['lr']} TB {r['tb']}"

        embed = discord.Embed(title="📋 MUKSCAN Professional Report", color=0xFFD700)
        embed.set_thumbnail(url=img_url)
        embed.description = response.text
        embed.set_footer(text=footer_text)

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

    status_msg = await ctx.send("🔍 MUKSCAN is looking into that...")

    system_prompt = """You are MUKSCAN, a Pokémon and TCG expert assistant. You ONLY answer questions related to:
    - Pokémon TCG cards, sets, rarities, and collecting
    - TCG stores, local game stores (LGS), card shops
    - Pokémon events, conventions, tournaments, prereleases
    - New set releases, product drops, and collection announcements
    - Card grading (PSA, CGC, BGS) and investing
    - General Pokémon game and franchise news relevant to collectors

    If a question is completely unrelated to Pokémon or TCG, politely decline and remind the user what you can help with.

    Always use Google Search to find current, accurate information — especially for:
    - Store locations (use the zip code or address provided)
    - Upcoming events and conventions
    - New set release dates and products
    - Current news in the Pokémon TCG community

    IMPORTANT — When searching for product drops and collection releases, search ALL of the following separately:
    - Official Pokémon TCG announcements (pokemoncenter.com, pokemon.com)
    - Retailer-exclusive products: search "Sam's Club Pokémon exclusive", "Best Buy Pokémon exclusive", "Costco Pokémon", "Target Pokémon exclusive", "Walmart Pokémon exclusive" separately
    - Retailer sign-up events: search "Best Buy Pokémon sign up event", "Sam's Club Pokémon White Flare exclusive"
    - Fan communities: search "Pokémon TCG exclusive drops this week reddit" and "pokebeach new products"
    - Do NOT limit results to only official TPCi announcements — retailer exclusives are confirmed real products and must be included

    FORMAT your responses like this for product/event listings:

    ## [Topic Title]

    ━━━━━━━━━━━━━━━━━━━━━━
    🛍️ **[Product or Event Name]**
    ┣ 📍 Where: [retailer or location]
    ┣ 📅 Date: [date or TBD]
    ┣ 🎟️ Sign-up required: [Yes/No]
    ┗ 📝 Notes: [brief detail]

    [repeat block for each product/event]

    For store lookups, list each store as:
    🏪 **[Store Name]**
    ┣ 📍 [Address]
    ┣ 📞 [Phone if available]
    ┗ 🕐 [Hours if available]

    For general questions, respond conversationally without heavy formatting.
    Keep responses concise and scannable. No walls of text."""

    try:
        contents = [
            {"role": "user", "parts": [{"text": system_prompt}]},
            {"role": "model", "parts": [{"text": "Understood! I'm MUKSCAN, your Pokémon and TCG expert. Ask me anything about cards, stores, events, or collecting!"}]}
        ]
        contents.extend(ask_history[user_id])

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        reply = response.text

        ask_history[user_id].append({
            "role": "model",
            "parts": [{"text": reply}]
        })

        chunks = [reply[i:i+4000] for i in range(0, len(reply), 4000)]

        await status_msg.delete()

        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="🔍 MUKSCAN Assistant" if i == 0 else "🔍 MUKSCAN Assistant (continued)",
                description=chunk,
                color=0x3498db
            )
            if i == len(chunks) - 1:
                embed.set_footer(text="Reply with !ask to follow up | !clearchat to reset")
            await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Ask Error: {str(e)}")


# --- COMMAND: !clearchat ---
@bot.command()
async def clearchat(ctx):
    user_id = ctx.author.id
    if user_id in ask_history:
        del ask_history[user_id]
    await ctx.send("🗑️ Your conversation history has been cleared. Fresh start!")


bot.run(os.getenv('DISCORD_TOKEN'))
