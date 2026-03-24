import discord
from discord.ext import commands
import google.generativeai as genai
import os
import requests
import random
from io import BytesIO

# 1. Setup Bot Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 2. Setup Gemini (Specifying the stable model)
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
# Using 'gemini-1.5-flash' is the most stable across all regions
model = genai.GenerativeModel('gemini-1.5-flash')

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN is live and squinting at cards!')

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

    # Bobby Lee style flavor text
    random_intro = [
        "🧐 MUKSCAN is squinting at your card... hold on.",
        "Wait, wait, wait... let me put my glasses on... okay, looking.",
        "Uh oh, is that a scratch? Or is that just a hair on my screen? Checking...",
        "Deep breath... analyzing your retirement fund right now."
    ]
    await ctx.send(random.choice(random_intro))

    # Download image
    try:
        response = requests.get(attachment.url)
        img_data = BytesIO(response.content).read()
    except Exception as e:
        await ctx.send("❌ Failed to download the image. Try again!")
        return

    # The "Grader" Prompt
    prompt = """
    You are a professional PSA card grader with a slightly humorous but strict personality. 
    Analyze this Pokémon card image and provide:
    1. **Card Identity**: Name, Set, and Number.
    2. **Centering**: Estimate L/R and T/B ratios.
    3. **Condition Details**: Note any whitening or surface issues.
    4. **Predicted PSA Grade**: A number from 1-10.
    
    Format the response with bold headers and keep it concise for a Discord embed.
    """

    try:
        # Generate content
        contents = [
            prompt,
            {'mime_type': 'image/jpeg', 'data': img_data}
        ]
        
        # Calling the model
        result = model.generate_content(contents)
        
        # Create Discord Embed
        embed = discord.Embed(title="MUKSCAN Grading Report", color=0xFFD700)
        embed.set_thumbnail(url=attachment.url)
        embed.description = result.text
        embed.set_footer(text="Grade is an estimate. Don't sue a Muk.")
        
        await ctx.send(embed=embed)

    except Exception as e:
        # Detailed error handling to see what's wrong in Discord
        error_msg = str(e)
        if "404" in error_msg:
            await ctx.send("⚠️ Google is playing games with the model name. Check Railway logs!")
        else:
            await ctx.send(f"⚠️ MUKSCAN had a brain fart: {error_msg}")

bot.run(os.getenv('DISCORD_TOKEN'))