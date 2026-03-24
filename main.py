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

# 2. Setup New Gemini SDK
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN is live and using the new Gemini SDK!')

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
        await ctx.send("📸 Please attach a photo or reply to one with `!grade`!")
        return

    await ctx.send("🧐 MUKSCAN is squinting at your card with the new SDK...")

    # Download image
    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()
    except Exception as e:
        await ctx.send("❌ Failed to download the image.")
        return

    prompt = """
    You are a professional PSA card grader. Analyze this Pokémon card image:
    1. Identify the Name, Set, and Number.
    2. Centering: Estimate L/R and T/B ratios.
    3. Condition: Look for whitening or surface issues.
    4. Grade: Provide a predicted PSA grade (1-10).
    Return the result in a clean, bolded format for Discord.
    """

    try:
        # The new way to call Gemini 
        response = client.models.generate_content(
            model='gemini-2.0-flash', # Using the newest 2026 stable model
            contents=[prompt, genai.types.Part.from_bytes(data=img_data, mime_type='image/jpeg')]
        )
        
        embed = discord.Embed(title="MUKSCAN Grading Report", color=0xFFD700)
        embed.set_thumbnail(url=attachment.url)
        embed.description = response.text
        embed.set_footer(text="Grade is an estimate. Muks don't have fingers, so be nice.")
        
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ MUKSCAN had a brain fart: {str(e)}")

bot.run(os.getenv('DISCORD_TOKEN'))