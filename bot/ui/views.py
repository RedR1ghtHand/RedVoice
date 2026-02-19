import discord
from discord import Interaction, ui

from utils import get_message

from .modals import RenameModal, SetLimitModal


class ChannelControlView(ui.View):
    def __init__(self, channel, owner, session_manager):
        super().__init__(timeout=None)
        self.channel = channel
        self.owner = owner
        self.session_manager = session_manager

    @ui.button(label=get_message("buttons.rename.label"), style=discord.ButtonStyle.primary, custom_id="rename_channel")
    async def rename_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(RenameModal(self.channel, self.owner, self.session_manager))

    @ui.button(label=get_message("buttons.increase_limit.label"), style=discord.ButtonStyle.success, custom_id="increase_channel_limit")
    async def increase_limit(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                get_message("buttons.increase_limit.msg_error"), ephemeral=True
            )
            return

        new_limit = min((self.channel.user_limit or 0) + 1, 99)
        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            get_message("buttons.increase_limit.msg_success", new_limit=new_limit),
            ephemeral=True
        )

    @ui.button(label=get_message("buttons.decrease_limit.label"), style=discord.ButtonStyle.danger, custom_id="decrease_channel_limit")
    async def decrease_limit(self, interaction: Interaction, button: ui.Button):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                get_message("buttons.decrease_limit.msg_error"), ephemeral=True
            )
            return

        new_limit = max((self.channel.user_limit or 0) - 1, 1)
        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            get_message("buttons.decrease_limit.msg_success", new_limit=new_limit),
            ephemeral=True
        )

    @ui.button(label=get_message("buttons.set_limit.label"), style=discord.ButtonStyle.secondary, custom_id="set_channel_limit")
    async def set_limit_modal(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(SetLimitModal(self.channel, self.owner))

        