import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import requests
import asyncio
import os

class Restore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="save_ids", description="Lưu ID thành viên của một server cụ thể")
    @app_commands.describe(guild_id="Nhập ID server muốn quét (để trống nếu muốn quét server hiện tại)")
    @app_commands.checks.has_permissions(administrator=True)
    async def save_ids(self, interaction: discord.Interaction, guild_id: str = None):
        """Lưu ID thành viên và tạo file theo ID/Tên server"""
        await interaction.response.defer(ephemeral=True) 
        
        # 1. Xác định server mục tiêu
        target_guild = None
        if guild_id:
            target_guild = self.bot.get_guild(int(guild_id))
            if not target_guild:
                await interaction.followup.send("❌ Bot không ở trong server có ID này hoặc ID không hợp lệ!", ephemeral=True)
                return
        else:
            target_guild = interaction.guild

        member_count = 0
        # 2. Đặt tên file theo ID hoặc tên server (bỏ dấu cách để tránh lỗi file)
        safe_name = "".join(x for x in target_guild.name if x.isalnum())
        file_path = f"members_{target_guild.id}_{safe_name}.txt"
        
        try:
            from function import database
            with open(file_path, "w") as f:
                # Đảm bảo bot đã load đủ member của server đó
                members = target_guild.members
                for member in members:
                    if not member.bot:
                        f.write(f"{member.id}\n")
                        # Lưu ID vào database dự phòng
                        database.save_simple_id(member.id, target_guild.id)
                        member_count += 1
            
            file = discord.File(file_path)
            await interaction.followup.send(
                f"Đã quét server: **{target_guild.name}**\nĐã lưu {member_count} ID vào file!", 
                file=file, 
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi lưu ID: {e}", ephemeral=True)

    @app_commands.command(name="unban_all", description="Gỡ ban hàng loạt từ file server cụ thể")
    @app_commands.describe(guild_id="Nhập ID server muốn gỡ ban (để tìm đúng file đã lưu)")
    @app_commands.checks.has_permissions(administrator=True)
    async def unban_all(self, interaction: discord.Interaction, guild_id: str):
        """Gỡ ban dựa trên file ID server cụ thể"""
        await interaction.response.defer(ephemeral=True)
        
        # Tìm file dựa trên guild_id trong tên file
        file_path = None
        for file in os.listdir("."):
            if file.startswith(f"members_{guild_id}"):
                file_path = file
                break

        if not file_path or not os.path.exists(file_path):
            await interaction.followup.send(f"⚠️ Không tìm thấy file backup cho server ID `{guild_id}`.", ephemeral=True)
            return

        unban_count = 0
        not_banned = 0
        error_count = 0

        with open(file_path, "r") as f:
            user_ids = f.read().splitlines()

        for user_id in user_ids:
            try:
                user = await self.bot.fetch_user(int(user_id))
                await interaction.guild.unban(user, reason="Gỡ ban hàng loạt")
                unban_count += 1
                await asyncio.sleep(0.3) 
            except discord.NotFound:
                not_banned += 1
            except Exception:
                error_count += 1

        embed = discord.Embed(title=f"🔓 Kết quả gỡ ban (Server {guild_id})", color=discord.Color.green())
        embed.add_field(name="✅ Thành công", value=f"`{unban_count}`", inline=True)
        embed.add_field(name="ℹ️ Không bị ban", value=f"`{not_banned}`", inline=True)
        embed.add_field(name="❌ Lỗi", value=f"`{error_count}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="restore_members", description="Phục hồi thành viên qua OAuth2")
    @app_commands.checks.has_permissions(administrator=True)
    async def restore_members(self, interaction: discord.Interaction):
        """Kéo thành viên từ Database (OAuth2)"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            conn = sqlite3.connect('backup.db')
            c = conn.cursor()
            c.execute('SELECT user_id, access_token FROM oauth_members')
            rows = c.fetchall()
            conn.close()
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi Database: {e}", ephemeral=True)
            return

        if not rows:
            await interaction.followup.send("⚠️ Database trống!", ephemeral=True)
            return

        success = 0 
        already_in = 0
        failed = 0 
        unbanned = 0

        for user_id, token in rows:
            try:
                user = await self.bot.fetch_user(int(user_id))
                await interaction.guild.unban(user)
                unbanned += 1
            except:
                pass

            url = f"https://discord.com/api/v10/guilds/{interaction.guild_id}/members/{user_id}"
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json"
            }
            data = {"access_token": token}
            
            try:
                response = requests.put(url, headers=headers, json=data)
                if response.status_code == 201:
                    success += 1
                elif response.status_code == 204:
                    already_in += 1
                else:
                    failed += 1
                await asyncio.sleep(0.5) 
            except:
                failed += 1

        embed = discord.Embed(title="🛡️ KẾT QUẢ PHỤC HỒI", color=discord.Color.blue())
        embed.add_field(name="🔓 Đã gỡ ban", value=f"`{unbanned}`", inline=False)
        embed.add_field(name="Pulled", value=f"`{success}`", inline=True)
        embed.add_field(name="✅ Đã ở sẵn", value=f"`{already_in}`", inline=True)
        embed.add_field(name="❌ Thất bại", value=f"`{failed}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Restore(bot))