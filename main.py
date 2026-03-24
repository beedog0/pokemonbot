import discord
from discord.ext import commands
import google.generativeai as genai
import os
import requests
from io import BytesIO

# 1. Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Setup Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash-latest')
@bot.event
async def on_ready():
    print(f'✅ MUKSCAN (Gemini Edition) is online!')

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
        await ctx.send("📸 Please attach a card photo or reply to one with `!grade`!")
        return

    await ctx.send("🧐 MUKSCAN is squinting at your card... hold on.")

    # Download the image to send to Gemini
    response = requests.get(attachment.url)
    img_data = BytesIO(response.content).read()

    prompt = """
    You are a professional PSA card grader. Analyze this Pokémon card image:
    1. Identify the Name, Set, and Number.
    2. Centering: Estimate L/R and T/B ratios (e.g., 60/40).
    3. Condition: Look for whitening on edges/corners or surface scratches.
    4. Grade: Provide a predicted PSA grade (1-10).
    Keep the response short and formatted for Discord.
    """

    try:
        # Generate the grade
        result = model.generate_content([prompt, {'mime_type': 'image/jpeg', 'data': img_data}])
        
        embed = discord.Embed(title="MUKSCAN Gemini Report", color=0x00ff00)
        embed.set_thumbnail(url=attachment.url)
        embed.description = result.text
        embed.set_footer(text="Powered by Gemini 1.5 Flash")
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")

bot.run(os.getenv('DISCORD_TOKEN'))