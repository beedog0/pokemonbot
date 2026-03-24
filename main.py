import discord
from discord.ext import commands
from google import genai
import os
import requests
from io import BytesIO

# 1. Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 2. Setup Client (Ensure GEMINI_API_KEY is in Railway Variables)
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN Paid Tier is active using Gemini 2.5 Flash!')

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

    status_msg = await ctx.send("🧐 MUKSCAN is performing a professional analysis...")

    # Download image
    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()
    except Exception:
        await status_msg.edit(content="❌ Failed to download the image.")
        return

    # Professional Grader Prompt
    prompt = """
    Identify this Pokémon card (Name, Set, Number).
    Act as a strict PSA Grader. Evaluate:
    - Centering (L/R and T/B ratios)
    - Corners/Edges (look for whitening/silvering)
    - Surface (scratches/print lines)
    Provide a Predicted PSA Grade (1-10) and an estimated Market Value.
    Format the response for a clean Discord Embed. 
    NO footnotes, NO citations, NO search suggestions.
    """

    try:
        # Using the current stable 2026 model: gemini-2.5-flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')]
        )
        
        embed = discord.Embed(title="MUKSCAN Grading Report", color=0xFFD700)
        embed.set_thumbnail(url=attachment.url)
        embed.description = response.text
        embed.set_footer(text="Verified Paid Tier Grade")
        
        await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        await status_msg.edit(content=f"⚠️ MUKSCAN Error: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))