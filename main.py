import discord
from discord.ext import commands
import requests
import os

# 1. Setup Bot Intents (needed to read messages/images)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot is logged in as {bot.user}')

@bot.command()
async def grade(ctx):
    # Check if the user actually uploaded an image
    if not ctx.message.attachments:
        await ctx.send("📸 Please attach a clear photo of your card!")
        return

    img_url = ctx.message.attachments[0].url
    await ctx.send("🔍 Checking the vault... AI is analyzing your card.")

    # 2. Get your keys from Railway Environment Variables
    api_key = os.getenv('XIMILAR_API_KEY')
    
    # Ximilar Endpoint for Collectibles (Pokemon/TCG)
    endpoint = "https://api.ximilar.com/collectibles/v2/tcg_id"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    # This payload asks for BOTH ID and Grading data
    payload = {
        "records": [{"_url": img_url}],
        "grading": True,
        "calculate_centering": True
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        data = response.json()
        
        # 3. Digging out the data from the AI's "brain"
        record = data['records'][0]
        card_name = record.get('best_label', "Unknown Card")
        
        # Grading Data
        grading = record.get('_grading', {})
        centering = grading.get('centering_inspect', {})
        
        # Simple PSA Logic (You can tweak this math later!)
        # We'll use their internal 'grade' as a baseline
        predicted_grade = grading.get('grade', "N/A")

        # 4. Format the Discord Response
        embed = discord.Embed(title="AI Grade Report", color=0xFFD700)
        embed.add_field(name="Card", value=card_name, inline=False)
        embed.add_field(name="Predicted PSA", value=f"**{predicted_grade}**", inline=True)
        
        if centering:
            lr = centering.get('lr_ratio', "??")
            tb = centering.get('tb_ratio', "??")
            embed.add_field(name="Centering", value=f"L/R: {lr}\nT/B: {tb}", inline=True)

        await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("⚠️ Oops! The AI got confused. Make sure the photo is top-down and clear.")

bot.run(os.getenv('DISCORD_TOKEN'))