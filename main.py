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

# 2. Setup Gemini Client (Paid Tier)
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN is live with Grading and Price Check!')

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

    status_msg = await ctx.send("🧐 MUKSCAN is squinting at your card...")

    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()

        prompt = """
        Identify this Pokémon card (Name, Set, Number).
        Act as a strict PSA Grader. Provide sections for:
        **🃏 Card Identification**
        **📐 Centering**
        **💥 Corners & Edges**
        **✨ Surface**
        **📈 Predicted PSA Grade**
        **💰 Estimated Market Value**
        STRICT RULES: No JSON, no code blocks, no citations.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')]
        )
        
        embed = discord.Embed(title="📋 MUKSCAN Grading Report", color=0xFFD700)
        embed.set_thumbnail(url=attachment.url)
        embed.description = response.text
        embed.set_footer(text="Official MUKSCAN PSA Estimate")
        
        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")

# --- COMMAND: !price ---
@bot.command()
async def price(ctx, *, card_name: str = None):
    # If they didn't type a name, check if they are replying to a grading report
    target_query = card_name
    if not target_query and ctx.message.reference:
        ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if ref.embeds:
            # Tries to pull the card name from the previous grading report
            target_query = ref.embeds[0].description.split('\n')[1]

    if not target_query:
        await ctx.send("❓ Please provide a card name! Example: `!price Charizard Base Set 4/102` or reply to a grade report.")
        return

    status_msg = await ctx.send(f"💸 Searching market data for **{target_query}**...")

    try:
        # We use Gemini's built-in Google Search tool for live pricing
        price_prompt = f"Find the current market price for the Pokémon card: {target_query}. Provide the average 'Sold' price on eBay and the current 'Market Price' on TCGPlayer for Raw, PSA 9, and PSA 10 conditions. Keep it brief."
        
        # 'google_search' tool is a paid-tier feature
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=price_prompt,
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearchRetrieval())]
            )
        )

        embed = discord.Embed(title=f"💰 Market Value: {target_query}", color=0x2ecc71)
        embed.description = response.text
        embed.set_footer(text="Live data from eBay & TCGPlayer via Google Search")
        
        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ Price Check Error: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))