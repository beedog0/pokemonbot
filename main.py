import discord
from discord.ext import commands
import requests
import os

# 1. Setup Bot Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ MUKSCAN is logged in as {bot.user}')

@bot.command()
async def grade(ctx):
    attachment = None

    # Check if the message itself has an image
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
    
    # Check if the user is REPLYING to a message that has an image
    elif ctx.message.reference:
        referenced_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if referenced_msg.attachments:
            attachment = referenced_msg.attachments[0]

    if not attachment:
        await ctx.send("📸 Please attach a photo or reply to one with `!grade`!")
        return

    # Filter for image files only
    if not any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
        await ctx.send("❌ That doesn't look like an image file!")
        return

    img_url = attachment.url
    await ctx.send("🔍 Analyzing card... calculating centering and surface quality.")

    # 2. Get your keys from Railway Environment Variables
    api_key = os.getenv('XIMILAR_API_KEY')
    endpoint = "https://api.ximilar.com/collectibles/v2/tcg_id"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "records": [{"_url": img_url}],
        "grading": True,
        "calculate_centering": True
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        data = response.json()
        
        # 3. Extract the data
        if 'records' not in data or not data['records']:
            await ctx.send("⚠️ Ximilar API returned no data. Check your API key!")
            return

        record = data['records'][0]
        card_name = record.get('best_label', "Unknown Card")
        
        grading = record.get('_grading', {})
        centering = grading.get('centering_inspect', {})
        predicted_grade = grading.get('grade', "N/A")

        # 4. Format the Discord Response
        embed = discord.Embed(title="MUKSCAN AI Grade Report", color=0xFFD700)
        embed.set_thumbnail(url=img_url)
        embed.add_field(name="🃏 Card Identified", value=f"**{card_name}**", inline=False)
        embed.add_field(name="📈 PSA Estimate", value=f"**Grade: {predicted_grade}**", inline=True)
        
        if centering:
            lr = centering.get('lr_ratio', "??")
            tb = centering.get('tb_ratio', "??")
            embed.add_field(name="📐 Centering", value=f"L/R: {lr}\nT/B: {tb}", inline=True)

        embed.set_footer(text="Note: AI grading is an estimate only.")
        await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("⚠️ Oops! The AI had a brain fart. Try a clearer, top-down photo.")

bot.run(os.getenv('DISCORD_TOKEN'))