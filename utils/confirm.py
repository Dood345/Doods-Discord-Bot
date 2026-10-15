"""Confirmation cards for side-effecting AI tools.

The tool posts a card and returns immediately; nothing happens until the person who asked clicks Confirm.
"""

import logging
from typing import Awaitable, Callable, Optional

import discord

logger = logging.getLogger(__name__)

CONFIRM_TIMEOUT = 120  # seconds

# action(interaction) -> result text shown to the clicker; check(interaction) -> error text or None
Action = Callable[[discord.Interaction], Awaitable[str]]
Check = Callable[[discord.Interaction], Awaitable[Optional[str]]]


class ConfirmView(discord.ui.View):
    def __init__(self, owner_id: int, action: Action, check: Optional[Check] = None,
                 confirm_label: str = "Confirm", timeout: float = CONFIRM_TIMEOUT):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.action = action
        self.check = check
        self.message: Optional[discord.Message] = None
        self.done = False
        self.confirm.label = confirm_label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🎙️ Hands off, test subject. That button belongs to someone else.", ephemeral=True)
            return False
        return True

    def _disable(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            return
        self.done = True
        self._disable()
        self.stop()
        # Acknowledge within Discord's 3s window before doing slow work
        await interaction.response.edit_message(view=self)
        try:
            if self.check:
                error = await self.check(interaction)
                if error:
                    await interaction.followup.send(error, ephemeral=True)
                    return
            result = await self.action(interaction)
            await interaction.followup.send(result)
        except Exception as e:
            logger.exception("Confirmed action failed")
            await interaction.followup.send(f"⚠️ The experiment failed: {type(e).__name__}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.done:
            return
        self.done = True
        self._disable()
        self.stop()
        content = interaction.message.content if interaction.message else ""
        await interaction.response.edit_message(content=f"{content}\n*Cancelled.*", view=self)

    async def on_timeout(self):
        if self.done or self.message is None:
            return
        self.done = True
        self._disable()
        try:
            await self.message.edit(content=f"{self.message.content}\n*Expired.*", view=self)
        except discord.HTTPException:
            pass


async def post_confirmation(ctx, key: str, text: str, action: Action, check: Optional[Check] = None,
                            confirm_label: str = "Confirm") -> str:
    """Post a confirm card for ctx.user and return a PENDING note for the model."""
    if key in ctx.pending:
        return "PENDING: a confirmation card for this is already posted. Do not post another."
    if ctx.channel is None:
        return "ERROR: no channel to post a confirmation in."
    ctx.pending.add(key)
    view = ConfirmView(ctx.user.id, action, check, confirm_label=confirm_label)
    view.message = await ctx.channel.send(text, view=view)
    return ("PENDING: posted a confirmation button. NOTHING has happened yet; tell the user to click "
            f"'{confirm_label}' to go ahead. Do not say it is done.")
