import discord
from discord.ext import commands
from google import genai
import os
import requests
import random
from io import BytesIO

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

last_graded = {}


@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Professional is active!')


# --- COMMAND LIST ---
@bot.command(name='commands')
async def command_list(ctx):
    embed = discord.Embed(
        title="🤖 MUKSCAN Command List",
        description="Your professional Pokémon card grading assistant.",
        color=0xFFD700
    )

    embed.add_field(name="📸 !grade", value="Grade a card + price", inline=False)
    embed.add_field(name="🔄 !regrade", value="Fix card name", inline=False)
    embed.add_field(name="💰 !price", value="Full price breakdown", inline=False)
    embed.add_field(name="📊 !flip", value="Check flip potential", inline=False)
    embed.add_field(name="👥 !pop", value="PSA population", inline=False)

    embed.set_footer(text="MUKSCAN: The Gold Standard")
    await ctx.send(embed=embed)


# --- MAIN GRADE FUNCTION ---
async def run_grade(ctx, status_msg, img_data, img_url, override_card=None):

    if override_card:
        card_instruction = f"The card is confirmed to be: {override_card}. Do NOT re-identify it."
    else:
        card_instruction = """Identify the Pokémon card: name, set, number, rarity."""

    prompt = f"""
You are a professional PSA grader and market analyst.

{card_instruction}

STEP 2: Find CURRENT market pricing.

STRICT PRICING RULES (NO ESTIMATES):

RAW:
- Use eBay SOLD listings average
- Label: (eBay sold)

PSA 9 & PSA 10:
1. FIRST → TCGPlayer Market Price
   - Label: (TCGPlayer)
2. IF NOT FOUND → PriceCharting
   - Label: (PriceCharting)
3. IF BOTH FAIL → N/A

SEARCH QUERIES:
- "[card name] PSA 9 TCGPlayer"
- "[card name] PSA 10 TCGPlayer"
- "[card name] PSA 9 PriceCharting"
- "[card name] PSA 10 PriceCharting"

STRICT:
- NO estimates
- NO guessing
- NO active listings
- ONLY eBay SOLD, TCGPlayer, PriceCharting
- If no data → N/A

STEP 3: Grade card condition.

FORMAT EXACTLY:

# PSA X
## Card Name - Set - Number
**Rarity:** X

**Market Value:**
Raw: $X.XX (eBay sold)
PSA 9: $X.XX (TCGPlayer) or $X.XX (PriceCharting) or N/A
PSA 10: $X.XX (TCGPlayer) or $X.XX (PriceCharting) or N/A

---
**📐 Centering**
(analysis)

**💥 Condition**
(analysis)

**📝 Rationale**
(1 sentence)

RULES:
- NEVER say "data unavailable"
- ONLY price or N/A
- NO extra text
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
        for line in response.text.split('\n'):
            if line.startswith('##'):
                card_name = line.replace('##', '').strip()
                break

        last_graded[ctx.channel.id] = {"url": img_url, "card": card_name}

        embed = discord.Embed(title="📋 MUKSCAN Report", color=0xFFD700)
        embed.description = response.text
        embed.set_thumbnail(url=img_url)

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Error: {str(e)}")


# --- GRADE COMMAND ---
@bot.command()
async def grade(ctx):
    if not ctx.message.attachments:
        await ctx.send("Attach a card image.")
        return

    attachment = ctx.message.attachments[0]
    status_msg = await ctx.send("🧐 Grading...")

    img = requests.get(attachment.url).content
    await run_grade(ctx, status_msg, img, attachment.url)


# --- RE-GRADE ---
@bot.command()
async def regrade(ctx, *, correction: str):
    cached = last_graded.get(ctx.channel.id)

    if not cached:
        await ctx.send("No previous card.")
        return

    status_msg = await ctx.send("🔄 Regrading...")

    img = requests.get(cached["url"]).content
    await run_grade(ctx, status_msg, img, cached["url"], override_card=correction)


# --- PRICE COMMAND ---
@bot.command()
async def price(ctx, *, card_name: str):
    status_msg = await ctx.send("💸 Checking prices...")

    prompt = f"""
Find prices for: {card_name}

Raw:
- eBay SOLD only

PSA 1–10:
- TCGPlayer first
- PriceCharting fallback
- If none → N/A

NO estimates.

FORMAT:

## {card_name}

Raw: $X (eBay sold)

PSA 9: $X (TCGPlayer/PriceCharting) or N/A
PSA 10: $X (TCGPlayer/PriceCharting) or N/A
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())]
            )
        )

        embed = discord.Embed(title="💰 Price Report", description=response.text, color=0x2ecc71)

        await status_msg.delete()
        await ctx.send(embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Error: {str(e)}")


bot.run(os.getenv('DISCORD_TOKEN'))