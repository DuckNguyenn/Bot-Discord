import discord
from discord import app_commands
from discord.ext import commands

ID_ADMIN = 1126531490793148427 

# --- ID CÁC ROLE CẢNH BÁO ---
ROLE_1_CO = 1476252108809437375  # ID Role "1 cờ"
ROLE_2_CO = 1476252177747018004  # ID Role "2 cờ"
ROLE_3_CO = 1476252224639471616  # ID Role "3 cờ"
ROLE_BANNED_NAM = 1476252275956777054  # ID Role "banned nấm"

def check_quyen(interaction: discord.Interaction) -> bool:
    return interaction.user.id == ID_ADMIN

class PuffWarn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 1. SLASH COMMAND: /warn @user [ly_do]
    @app_commands.command(name="warn_puff", description="warn")
    @app_commands.check(check_quyen)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member, ly_do: str = "Không có lý do"):
        await self.execute_warn(interaction, member, ly_do)

    # 2. PREFIX COMMAND: ?warn id [ly_do]
    @commands.command(name="warn")
    async def warn_prefix(self, ctx, member: discord.Member, *, ly_do: str = "Không có lý do"):
        if ctx.author.id != ID_ADMIN:
            await ctx.send("Down à mà dùng?", delete_after=5)
            return
        await self.execute_warn(ctx, member, ly_do)

    # --- LOGIC XỬ LÝ WARN CHUNG ---
    async def execute_warn(self, ctx, member: discord.Member, ly_do: str):
        is_slash = isinstance(ctx, discord.Interaction)
        current_role_ids = [role.id for role in member.roles]

        if ROLE_3_CO in current_role_ids:
            role_to_add = member.guild.get_role(ROLE_BANNED_NAM)
            await member.add_roles(role_to_add)
            status = "lần 4 -> Nhận role **Banned nấm**"
        elif ROLE_2_CO in current_role_ids:
            role_to_add = member.guild.get_role(ROLE_3_CO)
            await member.add_roles(role_to_add)
            status = "lần 3 -> Nhận role **3 cờ**"
        elif ROLE_1_CO in current_role_ids:
            role_to_add = member.guild.get_role(ROLE_2_CO)
            await member.add_roles(role_to_add)
            status = "lần 2 -> Nhận role **2 cờ**"
        else:
            role_to_add = member.guild.get_role(ROLE_1_CO)
            if role_to_add:
                await member.add_roles(role_to_add)
                status = "lần đầu -> Nhận role **1 cờ**"
            else:
                status = "Lỗi: Không tìm thấy ID Role"

        msg = f"{member.mention} đã bị cảnh báo {status}!\n**Lý do:** {ly_do}"

        if is_slash:
            await ctx.response.send_message(msg)
        else:
            await ctx.send(msg)

    @warn_slash.error
    async def quyen_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Down à mà dùng?", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PuffWarn(bot))