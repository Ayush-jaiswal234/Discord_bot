import discord

class MyPersistentView(discord.ui.View):
    def __init__(self,role):
        super().__init__(timeout=None)
        self.role = role

    @discord.ui.button(label="Get Role", custom_id="add", style=discord.ButtonStyle.blurple)
    async def get_role_callback(self, interaction, button):
        if self.role not in interaction.user.roles:
            await interaction.user.add_roles(self.role)
            await interaction.response.send_message(f"<@&{self.role.id}> role has been added!", ephemeral=True)
        else:
            await interaction.response.send_message(f"You already have the role <@&{self.role.id}>.", ephemeral=True)    

    @discord.ui.button(label="Remove role", custom_id="remove", style=discord.ButtonStyle.blurple)
    async def remove_role_callback(self, interaction, button):
        if self.role in interaction.user.roles:
            await interaction.user.remove_roles(self.role)
            await interaction.response.send_message(f"<@&{self.role.id}> role has been removed!", ephemeral=True)
        else:
            await interaction.response.send_message(f"You don't have the role <@&{self.role.id}>.", ephemeral=True)  