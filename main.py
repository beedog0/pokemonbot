import discord
from discord.ext import commands
import requests
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')

@bot.command()
async def grade(ctx):
    if not ctx.message.attachments:
        await ctx.send("Please upload a photo of the card!")
        return

    img_url = ctx.message.attachments[0].url
    await ctx.send("🔍 Analyzing your card with AI...")
    
    # We will use Railway environment variables for the API Key
    api_key = os.getenv('XIMILAR_API_KEY')
    headers = {"Authorization": f"Token {api_key}"}
    
    # Calling the Ximilar Collectibles/Grading API
    payload = {
        "records": [{"_url": img_url}],
        "grading": True
    }
    
    r = requests.post("https://api.ximilar.com/collectibles/v2/tcg_id", json=payload, headers=headers)
    data = r.json()
    
    # Basic data extraction - you can make this fancier later!
    try:
        best_match = data['records'][0]['best_label']
        # This is where you'd parse the grading_score or centering
        await ctx.send(f"✅ **Match Found:** {best_match}\n📈 **PSA Estimate:** (Logic coming soon!)")
    except:
        await ctx.send("❌ Could not identify card. Make sure it's a clear photo!")

bot.run(os.getenv('DISCORD_TOKEN'))