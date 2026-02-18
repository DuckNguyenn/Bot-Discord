import discord
from discord import app_commands
from discord.ext import commands

class Scripts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # --- MỤC THÊM SCRIPT MỚI TẠI ĐÂY ---
        # Sử dụng dấu nháy ba """ để bao bọc các script nhiều dòng hoặc chứa dấu ngoặc kép
        self.script_list = {
            "atlas": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Chris12089/atlasbss/main/script.lua"))()',
            
            "vichop": """getgenv().Config = {
    ["Field Accept"] = {
        Enable = true,
        ["Field Name"] = {
            "Pepper",
            "Rose",
            "Mountain",
            "Spider"
        }
    }
}
loadstring(game:HttpGet("https://api.jnkie.com/api/v1/luascripts/public/8839ce9fd98107fcf5cfeb9d3178c6de77e1060ee1e741025f95ca78fd42dc78/download"))()""",
            
            # "coco": 'loadstring(game:HttpGet("https://raw.githubusercontent.com/example/coco.lua"))()',
        }

    @app_commands.command(name="script", description="Lấy mã script theo tên")
    @app_commands.describe(ten="Tên script muốn lấy")
    async def get_script(self, interaction: discord.Interaction, ten: str):
        # Chuyển tên về chữ thường để tránh lỗi viết hoa viết thường
        ten_clean = ten.lower()
        
        if ten_clean in self.script_list:
            script_content = self.script_list[ten_clean]
            
            # Gửi script vào trong một khối code để dễ copy
            embed = discord.Embed(
                color=discord.Color.gold()
            )
            embed.description = f"```lua\n{script_content}\n```"            
            await interaction.response.send_message(embed=embed)
        else:
            # Nếu không tìm thấy tên trong danh sách
            danh_sach = ", ".join(self.script_list.keys())
            await interaction.response.send_message(
                f"❌ Không tìm thấy script tên `{ten}`.\nCác script hiện có: `{danh_sach}`", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Scripts(bot))