from discord import Interaction, TextStyle, ui

from utils import get_message


class RenameModal(ui.Modal, title=get_message("modals.rename.title")):
    def __init__(self, channel, owner, session_manager):
        super().__init__()
        self.channel = channel
        self.owner = owner
        self.session_manager = session_manager

        self.name_input = ui.TextInput(
            label=get_message("modals.rename.name_label"),
            placeholder=get_message("modals.rename.name_placeholder"),
            max_length=33,
            style=TextStyle.short
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                get_message("modals.rename.msg_error_owner"), ephemeral=True
            )
            return

        new_name = self.name_input.value.strip()
        if not new_name:
            await interaction.response.send_message(
                get_message("modals.rename.msg_error_empty"), ephemeral=True
            )
            return

        await self.channel.edit(name=new_name)
        await self.session_manager.update_channel_name(self.channel.id, new_name)
        await interaction.response.send_message(
            get_message("modals.rename.msg_success", new_name=new_name), ephemeral=True
        )


class SetLimitModal(ui.Modal, title=get_message("modals.set_limit.title")):
    def __init__(self, channel, owner):
        super().__init__()
        self.channel = channel
        self.owner = owner

        self.limit_input = ui.TextInput(
            label=get_message("modals.set_limit.limit_label"),
            placeholder=get_message("modals.set_limit.limit_placeholder"),
            style=TextStyle.short,
            max_length=2,
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: Interaction):
        if self.owner is not None and interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                get_message("modals.set_limit.msg_error_owner"), ephemeral=True
            )
            return

        try:
            new_limit = int(self.limit_input.value)
            if new_limit < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                get_message("modals.set_limit.msg_error_invalid"), ephemeral=True
            )
            return

        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            get_message("modals.set_limit.msg_success", new_limit=new_limit), ephemeral=True
        )
