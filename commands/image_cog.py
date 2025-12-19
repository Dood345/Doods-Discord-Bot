import io
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.image_gen import generate_image, is_comfy_online

logger = logging.getLogger(__name__)

class ImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="imagine", description="Generate an image via ComfyUI (Enhanced by Gemini)")
    async def imagine(self, interaction: discord.Interaction, prompt: str):
        # Defer immediately as this can take time
        await interaction.response.defer() 

        # 0. Fast Status Check
        if not await self.bot.loop.run_in_executor(None, is_comfy_online):
             await interaction.followup.send("🔌 **Service Unavailable:** ComfyUI is currently offline. Please try again later.")
             return

        try:
            # 1. Safety Check and Enhancement
            enhanced_prompt = prompt
            
            if hasattr(self.bot, 'ai_handler') and self.bot.ai_handler.is_available():
                # Notify user we are enhancing
                await interaction.followup.send(f"🎨 **Processing Request:** *{prompt}*\n✨ Enhancing prompt and checking safety...", ephemeral=True)
                
                enhanced_prompt = await self.bot.ai_handler.enhance_image_prompt(prompt)
                
                if enhanced_prompt == "SAFE_REFUSAL":
                    await interaction.channel.send(f"🚫 **Request Denied:** I cannot generate that image due to safety guidelines (Too horny/Child Safety/CSAM Protection).")
                    return # Exit cleanly
            
            # Update status
            msg = await interaction.channel.send(f"🖌️ **Generating:** *{enhanced_prompt}*\n(This may take a moment...)")

            # 2. Generate Image (Blocking call in executor)
            image_bytes = await self.bot.loop.run_in_executor(None, generate_image, enhanced_prompt)
            
            if image_bytes:
                file = discord.File(io.BytesIO(image_bytes), filename="generated.png")
                await msg.delete() # Remove the status message
                await interaction.channel.send(f"🖼️ **Result for:** *{prompt}*\n**Enhanced Prompt:** *{enhanced_prompt}*", file=file)
            else:
                await msg.edit(content=f"⚠️ **Generation Failed:** Could not connect to ComfyUI or an error occurred.")
        
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            await interaction.followup.send(f"❌ **Error:** Something went wrong: {e}")

async def setup(bot):
    await bot.add_cog(ImageCog(bot))
