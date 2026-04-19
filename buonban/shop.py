import discord
from discord import app_commands
from discord.ext import commands
from function import db_compat as sqlite3
from datetime import datetime

# --- VIEW ĐIỀU HƯỚNG MULTI-EMBED (CÓ KHÓA NGƯỜI DÙNG) ---
class ShopNavView(discord.ui.View):
    def __init__(self, data, user_id, current_index=0):
        super().__init__(timeout=120)
        self.data = data
        self.user_id = user_id # Lưu ID người gọi lệnh
        self.index = current_index
        self.page_index = 0 

    # Hàm kiểm tra quyền bấm nút
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Chỉ tương tác với bảng của mình thôi! Dùng /shop acc để xem", ephemeral=True)
            return False
        return True

    def create_embeds(self):
        row = self.data[self.index]
        acc_id, _, desc, all_images, timestamp = row
        images = [img.strip() for img in all_images.split(',') if img.strip()]
        
        start = self.page_index * 4
        current_images = images[start : start + 4]
        total_pages = (len(images) + 3) // 4
        
        # URL làm key để Discord gom nhóm lưới 4 ảnh
        grid_url = "https://discord.com" 

        embeds = []
        for i, img_url in enumerate(current_images):
            if i == 0:
                embed = discord.Embed(
                    title=f"Shop acc bss ({self.index + 1}/{len(self.data)})",
                    description=desc,
                    url=grid_url,
                    color=discord.Color.orange(),
                    timestamp=datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                )
                img_info = f" | Trang ảnh {self.page_index + 1}/{total_pages}"
                embed.set_footer(text=f"ID Acc: {acc_id}{img_info} | < > Đổi Acc | << >> Lướt trang ảnh")
            else:
                embed = discord.Embed(url=grid_url)
            
            embed.set_image(url=img_url)
            embeds.append(embed)
            
        return embeds

    @discord.ui.button(label="<<", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.data[self.index]
        images = [img.strip() for img in row[3].split(',') if img.strip()]
        total_pages = (len(images) + 3) // 4
        self.page_index = (self.page_index - 1) % total_pages
        await interaction.response.edit_message(embeds=self.create_embeds(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.gray)
    async def prev_acc(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.data)
        self.page_index = 0
        await interaction.response.edit_message(embeds=self.create_embeds(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.gray)
    async def next_acc(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.data)
        self.page_index = 0
        await interaction.response.edit_message(embeds=self.create_embeds(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.data[self.index]
        images = [img.strip() for img in row[3].split(',') if img.strip()]
        total_pages = (len(images) + 3) // 4
        self.page_index = (self.page_index + 1) % total_pages
        await interaction.response.edit_message(embeds=self.create_embeds(), view=self)

# --- CLASS CHÍNH ---
class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'shop_acc_v2.db'
        self.ID_ADMIN = 1126531490793148427 
        self.init_db()

    def init_db(self):
        sqlite3.ensure_all_tables()

    shop_group = app_commands.Group(name="shop", description="Shop acc bss")

    @shop_group.command(name="add_account", description="Thêm acc (Kèm ảnh chính)")
    async def add_account(self, interaction: discord.Interaction, hinh_anh: discord.Attachment, mo_ta: str):
        if interaction.user.id != self.ID_ADMIN:
            await interaction.response.send_message("Down à mà dùng?", ephemeral=True) 
            return
        desc_fix = mo_ta.replace("\\n", "\n")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT INTO accounts (guild_id, description, all_images, timestamp) VALUES (?, ?, ?, ?)', 
                  (interaction.guild_id, desc_fix, hinh_anh.url, now))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        await interaction.response.send_message(f"Đã tạo ID: `{new_id}`. Dùng `!shop_img {new_id}` để thêm ảnh.", ephemeral=True)

    @commands.command(name="shop_img")
    async def shop_img(self, ctx, acc_id: int):
        if ctx.author.id != self.ID_ADMIN or not ctx.message.attachments: return
        new_links = [at.url for at in ctx.message.attachments if at.content_type.startswith("image")]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT all_images FROM accounts WHERE id = ?', (acc_id,))
        row = c.fetchone()
        if row:
            combined = row[0] + "," + ",".join(new_links)
            c.execute('UPDATE accounts SET all_images = ? WHERE id = ?', (combined, acc_id))
            conn.commit()
            await ctx.send(f"Đã thêm {len(new_links)} ảnh vào ID `{acc_id}`!")
        conn.close()

    @shop_group.command(name="acc", description="Xem danh sách account")
    async def view_acc(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT * FROM accounts')
        rows = c.fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("Kho trống!", ephemeral=True)
            return
        # Truyền ID người gọi lệnh (interaction.user.id) vào View
        view = ShopNavView(rows, interaction.user.id)
        await interaction.response.send_message(embeds=view.create_embeds(), view=view)

    @shop_group.command(name="delete_account", description="Xóa acc")
    async def delete_account(self, interaction: discord.Interaction, ids: str):
        if interaction.user.id != self.ID_ADMIN: return
        id_list = [int(i.strip()) for i in ids.split(',') if i.strip().isdigit()]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        placeholders = ', '.join(['?'] * len(id_list))
        c.execute(f'DELETE FROM accounts WHERE id IN ({placeholders})', id_list)
        conn.commit()
        conn.close()
        await interaction.response.send_message("Đã xóa xong.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Shop(bot))