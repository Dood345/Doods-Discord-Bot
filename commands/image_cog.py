import io
import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger(__name__)

class ImageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.images = bot.image_service

    @app_commands.command(name="imagine", description="Generate an image via ComfyUI (prompt enhanced by Cave)")
    async def imagine(self, interaction: discord.Interaction, prompt: str):
        # Defer immediately as this can take time
        await interaction.response.defer()

        blocked = self.images.check_available(interaction.user.id)
        if blocked:
            await interaction.followup.send(self.bot.dialogue.get("system", f"image_{blocked}"), ephemeral=True)
            return

        try:
            status_msg = await interaction.followup.send(
                self.bot.dialogue.get("system", "image_processing", prompt=prompt), wait=True)
            result = await self.images.generate(interaction.user.id, prompt)

            if result.status == "ok":
                file = discord.File(io.BytesIO(result.image), filename="generated.png")
                await status_msg.delete()
                await interaction.channel.send(
                    self.bot.dialogue.get("system", "image_success", prompt=prompt, enhanced_prompt=result.enhanced_prompt),
                    file=file)
            elif result.status == "refused":
                await status_msg.edit(content=self.bot.dialogue.get("system", "image_denied"))
            elif result.status in ("offline", "busy", "cooldown"):
                await status_msg.edit(content=self.bot.dialogue.get("system", f"image_{result.status}"))
            else:
                await status_msg.edit(content=self.bot.dialogue.get("system", "image_failed"))

        except Exception as e:
            logger.error(f"Image generation error: {e}")
            await interaction.followup.send(self.bot.dialogue.get("system", "image_error", error=type(e).__name__))

async def setup(bot):
    await bot.add_cog(ImageCog(bot))
