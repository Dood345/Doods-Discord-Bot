"""Confirmation cards for side-effecting AI tools.

The tool posts a card and returns immediately; nothing happens until the person who asked clicks Confirm.
The card is a Components v2 layout: the question and its buttons in one container, with the outcome
(confirmed / cancelled / expired) written into the card itself.
"""

import logging
from typing import Awaitable, Callable, Optional

import discord

from utils.layouts import APERTURE_ORANGE, clip

logger = logging.getLogger(__name__)

CONFIRM_TIMEOUT = 120  # seconds

# action(interaction) -> result text shown to the clicker; check(interaction) -> error text or None
Action = Callable[[discord.Interaction], Awaitable[str]]
Check = Callable[[discord.Interaction], Awaitable[Optional[str]]]


class ConfirmView(discord.ui.LayoutView):
    def __init__(self, owner_id: int, action: Action, check: Optional[Check] = None,
                 confirm_label: str = "Confirm", timeout: float = CONFIRM_TIMEOUT, text: str = "Confirm?"):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.action = action
        self.check = check
        self.message: Optional[discord.Message] = None
        self.done = False
        self.body = discord.ui.TextDisplay(clip(text, 3800))
        self.confirm = discord.ui.Button(label=confirm_label, style=discord.ButtonStyle.green, emoji="✅")
        self.cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.grey, emoji="✖️")
        self.confirm.callback = self._on_confirm
        self.cancel.callback = self._on_cancel
        self.add_item(discord.ui.Container(self.body, discord.ui.ActionRow(self.confirm, self.cancel),
                                           accent_colour=APERTURE_ORANGE))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🎙️ Hands off, test subject. That button belongs to someone else.", ephemeral=True)
            return False
        return True

    def _finish(self, note: str):
        self.done = True
        self.confirm.disabled = self.cancel.disabled = True
        self.body.content = clip(f"{self.body.content}\n-# {note}", 3990)
        self.stop()

    async def _on_confirm(self, interaction: discord.Interaction):
        if self.done:
            return
        self._finish("✅ Confirmed")
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

    async def _on_cancel(self, interaction: discord.Interaction):
        if self.done:
            return
        self._finish("✖️ Cancelled.")
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        if self.done or self.message is None:
            return
        self._finish("⌛ Expired.")
        try:
            await self.message.edit(view=self)
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
    view = ConfirmView(ctx.user.id, action, check, confirm_label=confirm_label, text=text)
    view.message = await ctx.channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())
    return ("PENDING: posted a confirmation button. NOTHING has happened yet; tell the user to click "
            f"'{confirm_label}' to go ahead. Do not say it is done.")
