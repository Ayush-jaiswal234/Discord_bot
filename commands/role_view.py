import discord

class TradeSelect(discord.ui.Select):
    def __init__(self,roles):
        placeholder = "What's the price to ping you?"
        print(roles)
        options = [discord.SelectOption(label=role.name,value=str(role.id)) for role in roles]
        super().__init__(placeholder=placeholder, min_values=0,max_values=len(options),options=options,custom_id="Trade_Role_Selecter")
        self.roles = roles

    async def callback(self, interaction):
        user = interaction.user
        added_role = []
        removed_role = []

        for role in self.roles:
            if str(role.id) in self.values and role not in user.roles:
                await user.add_roles(role)
                added_role.append(role.name)
            elif role in user.roles and str(role.id) not in self.values: 
                await user.remove_roles(role)
                removed_role.append(role.name)   
        
        response = ""
        if added_role:
            response = f"{response}Roles added:\n{added_role}\n"
        if removed_role:
            response = f"{response}Roles removed:\n{removed_role}"
        await interaction.response.send_message(response,ephemeral= True)

class MyPersistentView(discord.ui.View):
    def __init__(self,roles):
        super().__init__(timeout=None)
        self.add_item(TradeSelect(roles))