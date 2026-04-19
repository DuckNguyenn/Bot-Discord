import ast
import asyncio
import json
import math
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from function import db_compat as sqlite3

try:
    import cohere
except Exception:
    cohere = None

DB_PATH = "raobai_config.db"
ROOT_ADMIN = 1126531490793148427
BOT_PREFIXES = ("bot ", "!bot ", "/bot ")


def _extract_user(obj):
    if hasattr(obj, "user"):
        return obj.user
    return obj


def check_quyen(target) -> bool:
    user = _extract_user(target)
    if not user:
        return False

    if user.id == ROOT_ADMIN:
        return True

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM admins WHERE user_id = ?", (user.id,))
            if c.fetchone():
                return True

            user_roles = getattr(user, "roles", []) or []
            user_role_ids = [role.id for role in user_roles]
            if not user_role_ids:
                return False

            placeholders = ",".join("?" * len(user_role_ids))
            c.execute(
                f"SELECT role_id FROM roles WHERE role_id IN ({placeholders})",
                user_role_ids,
            )
            return c.fetchone() is not None
    except Exception:
        return False


class SafeCalculator(ast.NodeVisitor):
    ALLOWED_NODES = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
        ast.Call,
        ast.Name,
    )

    ALLOWED_FUNCS = {
        "abs": abs,
        "round": round,
        "sqrt": math.sqrt,
        "pow": pow,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    def visit(self, node):
        if not isinstance(node, self.ALLOWED_NODES):
            raise ValueError(f"Biểu thức không hợp lệ: {type(node).__name__}")
        return super().visit(node)

    def evaluate(self, expr: str) -> Any:
        tree = ast.parse(expr, mode="eval")
        self.visit(tree)
        return eval(
            compile(tree, "<calc>", "eval"),
            {"__builtins__": {}},
            self.ALLOWED_FUNCS,
        )


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def infer_response_type(content: str) -> str:
    lowered = content.lower()
    if lowered.startswith("http") and any(
        ext in lowered for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")
    ):
        return "image"
    return "text"


class RaobaiSelect(discord.ui.Select):
    def __init__(self, bot, db_path, img_cat_shop, options):
        super().__init__(
            placeholder="Nhấp để xem danh sách server...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.bot = bot
        self.db_path = db_path
        self.img_cat_shop = img_cat_shop

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_value = self.values[0]

        cog = self.bot.get_cog("Chat")
        if cog and hasattr(cog, "broadcast_raobai"):
            report_text, success, total = await cog.broadcast_raobai(selected_value)
            await interaction.followup.send(
                f"{report_text}\n\n**Tổng cộng thành công: {success}/{total}**",
                ephemeral=True,
            )
            return

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if selected_value == "ALL":
                c.execute("SELECT * FROM raobai_channels")
            else:
                s_id = int(selected_value)
                c.execute(
                    "SELECT * FROM raobai_channels WHERE guild_id = ?",
                    (s_id,),
                )
            rows = c.fetchall()

        success = 0
        report = []

        for _, c_id, g_name in rows:
            channel = self.bot.get_channel(c_id)
            if channel:
                try:
                    await channel.send(self.img_cat_shop)
                    success += 1
                    report.append(f"✅ Đã gửi tới `{g_name}`")
                    await asyncio.sleep(1)
                except discord.Forbidden:
                    report.append(f"❌ `{g_name}`: Lỗi quyền gửi bài")
                except Exception as e:
                    report.append(f"❌ `{g_name}`: Lỗi {e}")
            else:
                report.append(f"❓ `{g_name}`: Không tìm thấy kênh")

        result_msg = "**Báo cáo Rao Bài:**\n" + "\n".join(report)
        await interaction.followup.send(
            f"{result_msg}\n\n**Tổng cộng thành công: {success}/{len(rows)}**",
            ephemeral=True,
        )


class RaobaiView(discord.ui.View):
    def __init__(self, bot, db_path, img_cat_shop, options):
        super().__init__(timeout=120)
        self.add_item(RaobaiSelect(bot, db_path, img_cat_shop, options))


class Chat(commands.Cog):
    chatbot_group = app_commands.Group(
        name="chatbot", description="Quản lý bộ não của bot"
    )
    quyen_group = app_commands.Group(
        name="quyen", description="Quản lý quyền sử dụng bot"
    )

    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_PATH
        self.knowledge_cache: List[Dict[str, Any]] = []
        self.actions_cache: List[Dict[str, Any]] = []
        self.pending_actions: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.calc = SafeCalculator()
        self.co = None
        self.ai_enabled = False
        self.default_knowledge = {
            "MH": "https://image2url.com/r2/default/images/1772188399025-059f4532-b46c-4341-a2f3-44cac9212ec6.png",
            "qr": "https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png",
            "toi xin hua": "Trong trường hợp nhóm này bị điều tra bởi các cơ quan trực thuộc bộ công an (hoặc các tổ chức chính trị tương tự phục vụ cho nhà nước CHXHCNVN), tôi khẳng định mình không liên quan tới nhóm hoặc những cá nhân khác trong nhóm này. Tôi không rõ tại sao mình lại có mặt ở đây vào thời điểm này, có lẽ tài khoản của tôi đã được thêm bởi một bên thứ ba. Tôi cũng xin khẳng định rằng mình không hề giúp sức cho những hành động chống phá Đảng và nhà nước của các thành viên trong nhóm này.",
            "hoang luan 40k": "https://image2url.com/r2/default/images/1772295505216-f8e6d11a-b1fd-4cb8-abb1-b018a933664a.png",
            "tao ticket": "Tạo ticket cày thuê ở https://discord.com/channels/1381629179791016017/1466141224619737230, sau đó chọn mục đích tạo ticket nha. https://image2url.com/r2/default/videos/1773334019456-f2a13ca7-346c-4742-adf2-88e11eb61957.mp4",
            "tạo ticket": "Tạo ticket cày thuê ở https://discord.com/channels/1381629179791016017/1466141224619737230, sau đó chọn mục đích tạo ticket nha. https://image2url.com/r2/default/videos/1773334019456-f2a13ca7-346c-4742-adf2-88e11eb61957.mp4",
            "cat shop": "{cat_shop_img}",
        }
        self.init_db()
        self.reload_brain()
        self._init_ai_client()

    def init_db(self):
        sqlite3.ensure_all_tables()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            for trigger, response in self.default_knowledge.items():
                c.execute(
                    """INSERT OR IGNORE INTO learned_responses
                       (trigger, normalized_trigger, response_text, response_type, match_type, priority, enabled)
                       VALUES (?, ?, ?, ?, 'exact', 100, 1)""",
                    (
                        trigger,
                        normalize_text(trigger),
                        response,
                        infer_response_type(response),
                    ),
                )
            conn.commit()

    def reload_brain(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                """SELECT trigger, normalized_trigger, response_text, response_type, match_type,
                          priority, enabled, usage_count
                   FROM learned_responses
                   WHERE enabled = 1
                   ORDER BY priority ASC, trigger ASC"""
            )
            self.knowledge_cache = [dict(row) for row in c.fetchall()]

            c.execute(
                """SELECT action_name, trigger, normalized_trigger, action_type, payload,
                          match_type, priority, enabled, usage_count
                   FROM bot_actions
                   WHERE enabled = 1
                   ORDER BY priority ASC, action_name ASC"""
            )
            self.actions_cache = [dict(row) for row in c.fetchall()]

    def _init_ai_client(self):
        api_key = os.getenv("COHERE_API_KEY")
        if api_key and cohere is not None:
            try:
                self.co = cohere.AsyncClient(api_key)
                self.ai_enabled = True
            except Exception:
                self.co = None
                self.ai_enabled = False
        else:
            self.co = None
            self.ai_enabled = False

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_configs WHERE key = ?", (key,))
            row = c.fetchone()
            return row[0] if row else default

    def set_config(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO bot_configs (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def render_text(
        self,
        template: str,
        message: discord.Message,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        data = {
            "user": getattr(message.author, "display_name", str(message.author)),
            "mention": message.author.mention,
            "guild": message.guild.name if message.guild else "DM",
            "channel": getattr(message.channel, "name", "direct-message"),
            "content": message.content,
            "svv_link": self.get_config("svv_link", ""),
            "cat_shop_img": self.get_config("cat_shop_img", ""),
            "qr_fallback_img": self.get_config("qr_fallback_img", ""),
        }
        if extra:
            data.update(extra)
        try:
            return template.format(**data)
        except Exception:
            return template

    async def send_smart_message(
        self,
        destination,
        content: str,
        *,
        reply_to: Optional[discord.Message] = None,
    ):
        content = content or ""
        if len(content) <= 2000:
            if reply_to:
                return await reply_to.reply(content, mention_author=False)
            return await destination.send(content)

        chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]
        last_msg = None
        for index, chunk in enumerate(chunks):
            if index == 0 and reply_to:
                last_msg = await reply_to.reply(chunk, mention_author=False)
            else:
                last_msg = await destination.send(chunk)
        return last_msg

    def record_memory(self, message: discord.Message, role: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO conversation_memory (guild_id, channel_id, user_id, role, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    message.guild.id if message.guild else None,
                    getattr(message.channel, "id", None),
                    message.author.id
                    if role == "user"
                    else self.bot.user.id if self.bot.user else None,
                    role,
                    (content or "")[:2000],
                ),
            )
            conn.execute(
                """DELETE FROM conversation_memory
                   WHERE id NOT IN (
                     SELECT id FROM conversation_memory
                     WHERE channel_id = ?
                     ORDER BY id DESC LIMIT 40
                   ) AND channel_id = ?""",
                (
                    getattr(message.channel, "id", None),
                    getattr(message.channel, "id", None),
                ),
            )
            conn.commit()

    def get_recent_memory_text(
        self, channel_id: Optional[int], limit: int = 8
    ) -> str:
        if channel_id is None:
            return "Chưa có lịch sử gần đây."
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """SELECT role, content FROM conversation_memory
                   WHERE channel_id = ? ORDER BY id DESC LIMIT ?""",
                (channel_id, limit),
            )
            rows = list(reversed(c.fetchall()))
        if not rows:
            return "Chưa có lịch sử gần đây."
        return "\n".join(f"{role}: {content}" for role, content in rows)

    def queue_learning(self, message: discord.Message, content: Optional[str] = None):
        raw = (content if content is not None else message.content) or ""
        norm = normalize_text(raw)
        if not norm:
            return
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """SELECT id FROM learning_queue
                   WHERE normalized_content = ? AND status = 'pending'
                   ORDER BY id DESC LIMIT 1""",
                (norm,),
            )
            if c.fetchone():
                return
            c.execute(
                """INSERT INTO learning_queue
                   (guild_id, channel_id, user_id, username, content, normalized_content)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    message.guild.id if message.guild else None,
                    getattr(message.channel, "id", None),
                    message.author.id,
                    str(message.author),
                    raw[:2000],
                    norm,
                ),
            )
            conn.commit()

    def _pending_key(self, message: discord.Message) -> Tuple[int, int]:
        return getattr(message.channel, "id", 0), message.author.id

    def _set_pending_action(
        self,
        message: discord.Message,
        action: str,
        params: Dict[str, Any],
        summary: str,
    ):
        self.pending_actions[self._pending_key(message)] = {
            "action": action,
            "params": params,
            "summary": summary[:500],
        }

    def _get_pending_action(
        self, message: discord.Message
    ) -> Optional[Dict[str, Any]]:
        return self.pending_actions.get(self._pending_key(message))

    def _pop_pending_action(
        self, message: discord.Message
    ) -> Optional[Dict[str, Any]]:
        return self.pending_actions.pop(self._pending_key(message), None)

    def _is_confirmation(self, content: str) -> bool:
        text = normalize_text(content)
        return text in {
            "thuc hien di",
            "lam di",
            "ok lam di",
            "ok di",
            "oke di",
            "oke",
            "ok",
            "xac nhan",
            "dong y",
            "trien khai di",
            "gui di",
            "run di",
            "execute",
        }

    def _is_cancel(self, content: str) -> bool:
        text = normalize_text(content)
        return text in {"huy", "khong", "dung lai", "cancel", "stop"}

    def _looks_question_like(self, content: str) -> bool:
        raw = (content or "").strip().lower()
        norm = normalize_text(content)
        markers = [
            "?",
            "co phai",
            "co dung",
            "dung lenh",
            "duoc khong",
            "phai khong",
            "co nghi",
            "nghi la",
        ]
        return any(marker in raw or marker in norm for marker in markers)

    def _parse_qr_request(self, content: str) -> Optional[Dict[str, Any]]:
        text = normalize_text(content)
        if "qr" not in text:
            return None
        if any(k in text for k in ["qr goc", "qr original", "qr bank"]):
            return {"original": True}

        amount = None
        note = ""
        m = re.search(
            r"(?:gui|tao|lenh)?\s*(?:ma\s+)?qr\s+([0-9][0-9\.,]{0,15})",
            text,
        )
        if m:
            raw_amount = m.group(1).replace(".", "").replace(",", "")
            try:
                amount = int(raw_amount)
            except ValueError:
                amount = None

        if amount is None and "qr" in text and any(ch.isdigit() for ch in text):
            digits = re.findall(r"\d+", text)
            if digits:
                try:
                    amount = int(digits[0])
                except ValueError:
                    amount = None

        note_match = re.search(
            r"(?:noi dung|nd|content)\s*[:=\-]?\s*(.+)$",
            content,
            re.IGNORECASE,
        )
        if note_match:
            note = note_match.group(1).strip()

        if amount is None and any(k in text for k in ["gui qr", "gui ma qr", "tao qr"]):
            return {"amount": None, "content": note}
        if amount is not None:
            return {"amount": amount, "content": note}
        return None

    def _parse_voice_say_request(self, content: str) -> Optional[str]:
        raw = (content or "").strip()
        norm = normalize_text(raw)

        if (
            "noi" not in norm
            and "nói" not in raw.lower()
            and "doc" not in norm
            and "đọc" not in raw.lower()
            and "tts" not in norm
            and "speak" not in norm
        ):
            return None

        patterns = [
            r'(?:^|\s)(?:noi|nói|doc|đọc|tts|speak)\s+["“](.+?)["”]\s*$',
            r"(?:^|\s)(?:noi|nói|doc|đọc|tts|speak)\s+'(.+?)'\s*$",
            r"(?:^|\s)(?:noi|nói|doc|đọc|tts|speak)\s+(.+)$",
        ]

        for pattern in patterns:
            m = re.search(pattern, raw, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
                if text:
                    return text
        return None

    def _parse_music_request(self, content: str) -> Optional[Dict[str, Any]]:
        raw = (content or "").strip()
        norm = normalize_text(raw)

        play_patterns = [
            r'^(?:phat nhac|phát nhạc|mo nhac|mở nhạc|bat nhac|bật nhạc|play)\s+(.+)$',
            r'^(?:phat bai|phát bài|choi bai|chơi bài|mo bai|mở bài)\s+(.+)$',
            r'^(?:phat|choi|chơi|mở)\s+nhac\s+(.+)$',
            r'^(?:phat|choi|chơi|mở)\s+bai\s+(.+)$',
        ]

        for pattern in play_patterns:
            m = re.search(pattern, raw, re.IGNORECASE)
            if m:
                query = m.group(1).strip().strip('"').strip("'")
                if query:
                    return {"action": "music_play", "query": query}

        if any(k in norm for k in [
            "dung nhac", "dừng nhạc", "stop nhac", "stop music",
            "tat nhac", "tắt nhạc", "dung bai", "dừng bài"
        ]):
            return {"action": "music_stop"}

        if any(k in norm for k in [
            "tam dung nhac", "tạm dừng nhạc", "pause nhac", "pause music",
            "tam dung bai", "tạm dừng bài"
        ]):
            return {"action": "music_pause"}

        if any(k in norm for k in [
            "phat tiep", "phát tiếp", "tiep tuc nhac", "tiếp tục nhạc",
            "resume music", "resume nhac", "choi tiep", "chơi tiếp"
        ]):
            return {"action": "music_resume"}

        if any(k in norm for k in [
            "skip nhac", "skip bai", "bo qua bai", "bỏ qua bài", "next bai", "next bài"
        ]):
            return {"action": "music_skip"}

        return None

    def _build_intent_preview(self, action: str, params: Dict[str, Any]) -> str:
        if action == "voice_join":
            return "Mình hiểu bạn muốn bot **vào voice**. Gõ `thực hiện đi` để chạy."
        if action == "voice_leave":
            return "Mình hiểu bạn muốn bot **rời voice**. Gõ `thực hiện đi` để chạy."
        if action == "voice_say":
            text = (params.get("text") or "").strip()
            return f"Mình hiểu bạn muốn bot nói: **{text}**. Gõ `thực hiện đi` để chạy."

        if action == "music_play":
            query = (params.get("query") or "").strip()
            return f"Mình hiểu bạn muốn bot phát nhạc: **{query}**. Gõ `thực hiện đi` để chạy."
        if action == "music_stop":
            return "Mình hiểu bạn muốn bot **dừng nhạc**. Gõ `thực hiện đi` để chạy."
        if action == "music_pause":
            return "Mình hiểu bạn muốn bot **tạm dừng nhạc**. Gõ `thực hiện đi` để chạy."
        if action == "music_resume":
            return "Mình hiểu bạn muốn bot **phát tiếp nhạc**. Gõ `thực hiện đi` để chạy."
        if action == "music_skip":
            return "Mình hiểu bạn muốn bot **skip bài hiện tại**. Gõ `thực hiện đi` để chạy."

        if action == "qr":
            amount = params.get("amount")
            content = (params.get("content") or "").strip()
            if amount is None:
                return "Mình hiểu bạn muốn gửi QR nhưng đang thiếu số tiền. Gõ lại kiểu `@bot gửi qr 100000` hoặc thêm `nội dung ...`."
            if content:
                return f"Mình hiểu bạn muốn gửi QR **{amount:,} VNĐ** với nội dung **{content}**. Gõ `thực hiện đi` để chạy."
            return f"Mình hiểu bạn muốn gửi QR **{amount:,} VNĐ**. Gõ `thực hiện đi` để chạy."
        if action == "qr_original":
            return "Mình hiểu bạn muốn gửi QR gốc. Gõ `thực hiện đi` để chạy."
        if action == "momo":
            return "Mình hiểu bạn muốn gửi mã Momo. Gõ `thực hiện đi` để chạy."
        if action == "raobai":
            target = params.get("target", "ALL")
            if str(target).upper() == "ALL":
                return "Mình hiểu bạn muốn rao bài ở **tất cả server**. Gõ `thực hiện đi` để chạy."
            return f"Mình hiểu bạn muốn rao bài ở server **{target}**. Gõ `thực hiện đi` để chạy."
        if action == "send_cat_shop":
            return "Mình hiểu bạn muốn gửi bảng giá Cat Shop. Gõ `thực hiện đi` để chạy."
        if action == "send_svv":
            return "Mình hiểu bạn muốn gửi link SVV. Gõ `thực hiện đi` để chạy."
        if action == "send_beequip":
            return "Mình hiểu bạn muốn gửi danh sách Beequip thất lạc. Gõ `thực hiện đi` để chạy."
        return f"Mình hiểu bạn muốn chạy action `{action}`. Gõ `thực hiện đi` để chạy."

    def detect_natural_intent(
        self, content: str
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        norm = normalize_text(content)

        if any(
            k in norm
            for k in [
                "vao voice",
                "vo voice",
                "vao kenh voice",
                "vo kenh voice",
                "join voice",
                "join vc",
                "vao room",
                "vo room",
            ]
        ):
            return "voice_join", {}

        if any(
            k in norm
            for k in [
                "roi voice",
                "thoat voice",
                "ra khoi voice",
                "leave voice",
                "leave vc",
                "out voice",
            ]
        ):
            return "voice_leave", {}

        say_text = self._parse_voice_say_request(content)
        if say_text:
            return "voice_say", {"text": say_text}

        music_req = self._parse_music_request(content)
        if music_req:
            action = music_req.get("action")
            if action == "music_play":
                return "music_play", {"query": music_req.get("query", "")}
            if action == "music_stop":
                return "music_stop", {}
            if action == "music_pause":
                return "music_pause", {}
            if action == "music_resume":
                return "music_resume", {}
            if action == "music_skip":
                return "music_skip", {}

        if any(k in norm for k in ["rao bai", "raobai"]):
            if any(
                k in norm
                for k in [
                    "tat ca server",
                    "tat ca sv",
                    "all server",
                    "all sv",
                    "moi server",
                ]
            ):
                return "raobai", {"target": "ALL"}
            guild_match = re.search(r"(?:server|sv)\s+(\d{6,})", norm)
            if guild_match:
                return "raobai", {"target": guild_match.group(1)}
            return "raobai", {"target": "ALL"}

        qr_params = self._parse_qr_request(content)
        if qr_params:
            if qr_params.get("original"):
                return "qr_original", {}
            return "qr", {
                "amount": qr_params.get("amount"),
                "content": qr_params.get("content", ""),
            }

        if "momo" in norm:
            return "momo", {}

        if any(k in norm for k in ["bang gia", "cat shop"]):
            return "send_cat_shop", {}

        if any(k in norm for k in ["server vip", "svv"]):
            return "send_svv", {}

        if any(k in norm for k in ["beequip", "that lac"]):
            return "send_beequip", {}

        if any(
            k in norm
            for k in [
                "tao ticket",
                "mo ticket",
                "ticket ho tro",
                "khieu nai",
                "can ho tro",
            ]
        ):
            return "reply_text", {"text": self.default_knowledge["tạo ticket"]}

        return None

    def _try_math(self, content: str) -> Optional[str]:
        text = normalize_text(content)
        patterns = [r"(?:tinh|calc|math)\s+(.+)", r"^([0-9\s\+\-\*\/\(\)\.%]+)$"]
        for pattern in patterns:
            m = re.search(pattern, text)
            if not m:
                continue
            expr = m.group(1).strip().replace("x", "*").replace(":", "/")
            try:
                value = self.calc.evaluate(expr)
                return f"Kết quả: **{value}**"
            except Exception:
                continue
        return None

    def list_raobai_targets(self) -> List[Tuple[int, int, str]]:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT guild_id, channel_id, guild_name FROM raobai_channels ORDER BY guild_name COLLATE NOCASE"
            )
            return c.fetchall()

    async def broadcast_raobai(self, target: str) -> Tuple[str, int, int]:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if str(target).upper() == "ALL":
                c.execute("SELECT guild_id, channel_id, guild_name FROM raobai_channels")
            else:
                try:
                    guild_id = int(str(target))
                except ValueError:
                    return "❌ ID server không hợp lệ.", 0, 0
                c.execute(
                    "SELECT guild_id, channel_id, guild_name FROM raobai_channels WHERE guild_id = ?",
                    (guild_id,),
                )
            rows = c.fetchall()

        if not rows:
            return "❌ Không có server nào khớp cấu hình.", 0, 0

        img = self.get_config("cat_shop_img") or ""
        success = 0
        report = []
        for _, channel_id, guild_name in rows:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                report.append(f"❓ `{guild_name}`: Không tìm thấy kênh")
                continue
            try:
                await channel.send(img)
                success += 1
                report.append(f"✅ Đã gửi tới `{guild_name}`")
                await asyncio.sleep(1)
            except discord.Forbidden:
                report.append(f"❌ `{guild_name}`: Lỗi quyền gửi bài")
            except Exception as e:
                report.append(f"❌ `{guild_name}`: Lỗi {e}")

        return "**Báo cáo Rao Bài:**\n" + "\n".join(report), success, len(rows)

    async def run_raobai_internal(
        self, *, message: Optional[discord.Message] = None, target: str = "ALL"
    ):
        report_text, success, total = await self.broadcast_raobai(target)
        final_text = f"{report_text}\n\n**Tổng cộng thành công: {success}/{total}**"
        if message:
            await self.send_smart_message(
                message.channel, final_text, reply_to=message
            )
        return final_text

    async def send_beequip(self, channel: discord.abc.Messageable):
        links = [
            "https://image2url.com/r2/default/images/1772018251894-78fb3996-7b3f-4fda-9a76-e88ab64fc552.png",
            "https://image2url.com/r2/default/images/1772018293232-a4938fdd-cc08-432d-aece-93505cccbee5.png",
        ]
        await channel.send("Beequip thất lạc của bố, thằng nào lấy thì cẩn thận")
        for url in links:
            await channel.send(url)

    async def _try_external_action(
        self, action: str, params: Dict[str, Any], message: discord.Message
    ) -> bool:
        candidates_map = {
            "qr": [
                "send_qr_internal",
                "run_qr_internal",
                "qr_internal",
                "execute_qr",
                "handle_qr_intent",
            ],
            "qr_original": ["send_qr_internal", "run_qr_internal", "qr_internal"],
            "momo": ["send_momo_internal", "run_momo_internal", "momo_internal"],
            "voice_join": ["voice_join_internal"],
            "voice_leave": ["voice_leave_internal"],
            "voice_say": ["voice_say_internal"],
            "music_play": ["play_music_internal", "play_internal"],
            "music_stop": ["stop_music_internal"],
            "music_pause": ["pause_music_internal"],
            "music_resume": ["resume_music_internal"],
            "music_skip": ["skip_music_internal"],
        }

        candidates = candidates_map.get(action, [])
        if not candidates:
            return False

        preferred_cogs = []

        if action.startswith("voice_"):
            voice_cog = self.bot.get_cog("Voice")
            if voice_cog:
                preferred_cogs.append(voice_cog)

        if action.startswith("music_"):
            music_cog = self.bot.get_cog("Music")
            if music_cog:
                preferred_cogs.append(music_cog)

        for cog in self.bot.cogs.values():
            if cog is self:
                continue
            if cog not in preferred_cogs:
                preferred_cogs.append(cog)

        print(
            f"[CHAT] action={action} | cogs={[type(c).__name__ for c in preferred_cogs]}",
            flush=True,
        )

        for cog in preferred_cogs:
            for name in candidates:
                fn = getattr(cog, name, None)
                if fn is None:
                    continue

                print(f"[CHAT] trying {type(cog).__name__}.{name}", flush=True)

                try:
                    result = fn(message=message, **params)
                    if asyncio.iscoroutine(result):
                        result = await result

                    if isinstance(result, str) and result.strip():
                        await self.send_smart_message(
                            message.channel, result[:1995], reply_to=message
                        )
                    return True

                except TypeError:
                    try:
                        result = fn(**params)
                        if asyncio.iscoroutine(result):
                            result = await result

                        if isinstance(result, str) and result.strip():
                            await self.send_smart_message(
                                message.channel, result[:1995], reply_to=message
                            )
                        return True
                    except Exception as e:
                        print(
                            f"[CHAT] failed {type(cog).__name__}.{name} | error={e}",
                            flush=True,
                        )
                        continue

                except Exception as e:
                    print(
                        f"[CHAT] failed {type(cog).__name__}.{name} | error={e}",
                        flush=True,
                    )
                    continue

        return False

    async def execute_internal_action(
        self, action: str, params: Dict[str, Any], message: discord.Message
    ):
        action = (action or "").strip().lower()

        if action == "voice_join":
            if await self._try_external_action("voice_join", {}, message):
                return "internal:voice_join"
            text = "❌ Không tìm thấy voice handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "voice_leave":
            if await self._try_external_action("voice_leave", {}, message):
                return "internal:voice_leave"
            text = "❌ Không tìm thấy voice handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "voice_say":
            text_value = (params.get("text") or "").strip()
            if not text_value:
                text = "❌ Bạn chưa nhập nội dung để nói."
                await self.send_smart_message(message.channel, text, reply_to=message)
                return text
            if await self._try_external_action(
                "voice_say", {"text": text_value}, message
            ):
                return "internal:voice_say"
            text = "❌ Không tìm thấy voice handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "music_play":
            query = (params.get("query") or "").strip()
            if not query:
                text = "❌ Bạn chưa nhập tên bài hoặc link YouTube."
                await self.send_smart_message(message.channel, text, reply_to=message)
                return text

            if await self._try_external_action("music_play", {"query": query}, message):
                return "internal:music_play"

            text = "❌ Không tìm thấy music handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "music_stop":
            if await self._try_external_action("music_stop", {}, message):
                return "internal:music_stop"

            text = "❌ Không tìm thấy music handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "music_pause":
            if await self._try_external_action("music_pause", {}, message):
                return "internal:music_pause"

            text = "❌ Không tìm thấy music handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "music_resume":
            if await self._try_external_action("music_resume", {}, message):
                return "internal:music_resume"

            text = "❌ Không tìm thấy music handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "music_skip":
            if await self._try_external_action("music_skip", {}, message):
                return "internal:music_skip"

            text = "❌ Không tìm thấy music handler."
            await self.send_smart_message(message.channel, text, reply_to=message)
            return text

        if action == "raobai":
            target = str(params.get("target", "ALL"))
            await self.run_raobai_internal(message=message, target=target)
            return "internal:raobai"

        if action == "qr":
            amount = params.get("amount")
            content = params.get("content") or params.get("note") or ""
            if amount is None:
                text = "❌ Thiếu số tiền để gửi QR. Ví dụ: `@bot gửi qr 100000 nội dung abc`."
                await self.send_smart_message(message.channel, text, reply_to=message)
                return text
            if await self._try_external_action(
                "qr", {"amount": amount, "content": content}, message
            ):
                return "internal:qr"
            fallback = self.get_config("qr_fallback_img", "")
            text = (
                f"{fallback}\nSố tiền: **{amount:,} VNĐ**"
                if fallback
                else f"QR fallback\nSố tiền: **{amount:,} VNĐ**"
            )
            if content:
                text += f"\nNội dung: **{content}**"
            await self.send_smart_message(message.channel, text, reply_to=message)
            return "internal:qr_fallback"

        if action == "qr_original":
            if await self._try_external_action("qr_original", {"original": True}, message):
                return "internal:qr_original"
            fallback = self.get_config("qr_fallback_img", "")
            await self.send_smart_message(
                message.channel,
                fallback or "❌ Chưa có QR fallback.",
                reply_to=message,
            )
            return "internal:qr_original_fallback"

        if action == "momo":
            if await self._try_external_action("momo", {}, message):
                return "internal:momo"
            await self.send_smart_message(
                message.channel,
                "❌ Không tìm thấy handler Momo.",
                reply_to=message,
            )
            return "internal:momo_missing"

        if action == "send_cat_shop":
            img = self.get_config("cat_shop_img")
            await self.send_smart_message(
                message.channel,
                img or "❌ Chưa cấu hình ảnh bảng giá.",
                reply_to=message,
            )
            return "internal:send_cat_shop"

        if action == "send_svv":
            svv = self.get_config("svv_link")
            await self.send_smart_message(
                message.channel,
                svv or "❌ Chưa cấu hình link SVV.",
                reply_to=message,
            )
            return "internal:send_svv"

        if action == "send_beequip":
            await self.send_beequip(message.channel)
            return "internal:send_beequip"

        if action == "reply_text":
            template = str(params.get("text", ""))
            rendered = self.render_text(template, message)
            await self.send_smart_message(
                message.channel,
                rendered or "✅ Đã chạy action.",
                reply_to=message,
            )
            return rendered or "internal:reply_text"

        if action == "send_message":
            template = str(params.get("text", ""))
            rendered = self.render_text(template, message)
            await self.send_smart_message(message.channel, rendered or "✅ Đã chạy action.")
            return rendered or "internal:send_message"

        unknown = f"⚠️ Không hỗ trợ internal action `{action}`."
        await self.send_smart_message(message.channel, unknown, reply_to=message)
        return unknown

    async def _ask_ai(
        self, message: discord.Message, user_text: str
    ) -> Optional[str]:
        if not self.ai_enabled or not self.co:
            return None

        system_prompt = f"""
Bạn là AI quản lý shop trong Discord.
Mục tiêu:
- Trả lời ngắn gọn, đúng trọng tâm.
- Không bao giờ nói rằng đã thực hiện hành động nếu code chưa thực thi thật.
- Nếu người dùng đang yêu cầu tác vụ như QR, rao bài, bảng giá, SVV, ticket, voice, music thì ưu tiên nói ngắn gọn hoặc nhắc họ dùng câu trực tiếp hơn.
- Nếu không chắc, nói rõ là chưa chắc.

[KIẾN THỨC SHOP]
- Tạo ticket cày thuê ở https://discord.com/channels/1381629179791016017/1466141224619737230, sau đó chọn mục đích tạo ticket nha.
- Link SVV hiện tại: {self.get_config('svv_link', 'chưa cấu hình')}
- Ảnh bảng giá hiện tại: {self.get_config('cat_shop_img', 'chưa cấu hình')}

[LỊCH SỬ GẦN ĐÂY]
{self.get_recent_memory_text(getattr(message.channel, 'id', None))}
""".strip()

        try:
            response = await self.co.chat(
                model="command-r-plus-08-2024",
                message=user_text,
                preamble=system_prompt,
            )
            text = (response.text or "").strip()
            return text[:1995] if text else None
        except Exception:
            return None

    async def handle_targeted_chat(
        self, message: discord.Message, content: str
    ) -> bool:
        if self._is_cancel(content):
            if self._pop_pending_action(message):
                text = "🛑 Đã hủy hành động chờ thực hiện."
                await self.send_smart_message(message.channel, text, reply_to=message)
                self.record_memory(message, "assistant", text)
                return True

        if self._is_confirmation(content):
            pending = self._pop_pending_action(message)
            if pending:
                result = await self.execute_internal_action(
                    pending["action"], pending["params"], message
                )
                self.record_memory(message, "assistant", str(result)[:2000])
                return True
            text = "❌ Hiện không có hành động nào đang chờ để thực hiện."
            await self.send_smart_message(message.channel, text, reply_to=message)
            self.record_memory(message, "assistant", text)
            return True

        intent = self.detect_natural_intent(content)
        if intent:
            action, params = intent

            if action == "qr" and params.get("amount") is None:
                text = "❌ Bạn chưa ghi số tiền. Ví dụ: `@bot gửi qr 100000` hoặc `@bot gửi qr 100000 nội dung abc`."
                await self.send_smart_message(message.channel, text, reply_to=message)
                self.record_memory(message, "assistant", text)
                return True

            if self._looks_question_like(content):
                preview = self._build_intent_preview(action, params)
                self._set_pending_action(message, action, params, preview)
                await self.send_smart_message(
                    message.channel, preview, reply_to=message
                )
                self.record_memory(message, "assistant", preview)
                return True

            result = await self.execute_internal_action(action, params, message)
            self.record_memory(message, "assistant", str(result)[:2000])
            return True

        math_result = self._try_math(content)
        if math_result:
            await self.send_smart_message(
                message.channel, math_result, reply_to=message
            )
            self.record_memory(message, "assistant", math_result)
            return True

        if await self.answer_from_brain(message, content):
            return True

        ai_text = await self._ask_ai(message, content)
        if ai_text:
            await self.send_smart_message(message.channel, ai_text, reply_to=message)
            self.record_memory(message, "assistant", ai_text)
            self.queue_learning(message, content)
            return True

        self.queue_learning(message, content)
        fallback = (
            "Xin lỗi, tôi không hiểu yêu cầu của bạn. Bạn có thể nói rõ hơn được không?"
        )
        await self.send_smart_message(message.channel, fallback, reply_to=message)
        self.record_memory(message, "assistant", fallback)
        return True

    def is_chatbot_target(self, message: discord.Message) -> bool:
        raw = (message.content or "").strip()
        if not raw:
            return False

        if self.bot.user and self.bot.user in getattr(message, "mentions", []):
            return True

        for line in raw.splitlines():
            lowered = line.strip().lower()
            if any(lowered.startswith(prefix) for prefix in BOT_PREFIXES):
                return True

        return False

    def strip_bot_prefix(self, content: str) -> str:
        raw = content.strip()
        if self.bot.user:
            raw = raw.replace(self.bot.user.mention, " ")
        lowered = raw.lower().strip()
        for prefix in BOT_PREFIXES:
            if lowered.startswith(prefix):
                return raw[len(prefix) :].strip()
        return raw.strip()

    def extract_targeted_commands(self, message: discord.Message) -> List[str]:
        raw = (message.content or "").strip()
        if not raw:
            return []

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        commands_found: List[str] = []

        has_global_mention = bool(
            self.bot.user and self.bot.user in getattr(message, "mentions", [])
        )

        for line in lines:
            cleaned = line

            if self.bot.user:
                cleaned = cleaned.replace(self.bot.user.mention, " ")

            lowered = cleaned.lower().strip()
            matched_prefix = False

            for prefix in BOT_PREFIXES:
                if lowered.startswith(prefix):
                    cleaned = cleaned[len(prefix) :].strip()
                    matched_prefix = True
                    break

            if matched_prefix or has_global_mention:
                cleaned = cleaned.strip()
                if cleaned:
                    commands_found.append(cleaned)

        if not commands_found:
            stripped = self.strip_bot_prefix(raw)
            if stripped:
                commands_found.append(stripped)

        return commands_found

    async def handle_targeted_commands(self, message: discord.Message) -> bool:
        commands_found = self.extract_targeted_commands(message)
        if not commands_found:
            return False

        handled_any = False
        for cmd in commands_found:
            try:
                result = await self.handle_targeted_chat(message, cmd)
                handled_any = handled_any or result
            except Exception as e:
                await self.send_smart_message(
                    message.channel,
                    f"❌ Lỗi khi xử lý lệnh `{cmd}`: `{e}`",
                    reply_to=message,
                )

        return handled_any

    def get_fuzzy_threshold(self) -> float:
        try:
            return float(self.get_config("chatbot_fuzzy_threshold", "0.86"))
        except Exception:
            return 0.86

    def match_rule(
        self,
        content: str,
        rules: List[Dict[str, Any]],
        *,
        key_name: str = "response_text",
    ) -> Optional[Dict[str, Any]]:
        norm = normalize_text(content)
        if not norm:
            return None

        fuzzy_threshold = self.get_fuzzy_threshold()
        best_fuzzy: Optional[Tuple[float, Dict[str, Any]]] = None

        for rule in rules:
            rule_trigger = rule.get("normalized_trigger") or normalize_text(
                rule.get("trigger", "")
            )
            match_type = rule.get("match_type", "exact")

            if match_type == "exact" and norm == rule_trigger:
                return rule
            if match_type == "contains" and rule_trigger and rule_trigger in norm:
                return rule
            if match_type == "fuzzy" and rule_trigger:
                ratio = SequenceMatcher(None, norm, rule_trigger).ratio()
                if ratio >= fuzzy_threshold:
                    if not best_fuzzy or ratio > best_fuzzy[0]:
                        best_fuzzy = (ratio, rule)

        return best_fuzzy[1] if best_fuzzy else None

    def mark_rule_used(self, table: str, id_field: str, id_value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"""UPDATE {table}
                    SET usage_count = usage_count + 1,
                        last_used_at = CURRENT_TIMESTAMP
                    WHERE {id_field} = ?""",
                (id_value,),
            )
            conn.commit()

    async def execute_action(self, action: Dict[str, Any], message: discord.Message):
        action_type = action.get("action_type", "message")
        payload = action.get("payload", "")

        if action_type == "message":
            rendered = self.render_text(payload, message)
            sent = await self.send_smart_message(
                message.channel, rendered, reply_to=message
            )
            self.record_memory(message, "assistant", rendered)
            return sent

        if action_type == "internal":
            try:
                raw = json.loads(payload)
                if not isinstance(raw, dict):
                    raise ValueError("Payload internal phải là JSON object")
            except Exception as e:
                return await self.send_smart_message(
                    message.channel,
                    f"⚠️ Action `{action.get('action_name')}` bị lỗi JSON internal: {e}",
                    reply_to=message,
                )

            internal_name = str(
                raw.get("action") or raw.get("name") or raw.get("internal_action") or ""
            ).strip()
            params = raw.get("params", {})
            if not isinstance(params, dict):
                params = {}
            for key, value in raw.items():
                if key in {"action", "name", "internal_action", "params"}:
                    continue
                params.setdefault(key, value)

            result = await self.execute_internal_action(internal_name, params, message)
            self.record_memory(message, "assistant", str(result)[:2000])
            return result

        if action_type != "sequence":
            rendered = (
                f"⚠️ Action `{action.get('action_name')}` có kiểu không hỗ trợ: `{action_type}`"
            )
            return await self.send_smart_message(
                message.channel,
                rendered,
                reply_to=message,
            )

        try:
            steps = json.loads(payload)
            if not isinstance(steps, list):
                raise ValueError("Payload sequence phải là JSON array")
        except Exception as e:
            return await self.send_smart_message(
                message.channel,
                f"⚠️ Action `{action.get('action_name')}` bị lỗi JSON: {e}",
                reply_to=message,
            )

        last_msg = None
        assistant_notes = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_type = step.get("type", "message")
            if step_type in ("message", "reply"):
                rendered = self.render_text(str(step.get("content", "")), message)
                assistant_notes.append(rendered)
                if step_type == "reply":
                    last_msg = await self.send_smart_message(
                        message.channel, rendered, reply_to=message
                    )
                else:
                    last_msg = await self.send_smart_message(message.channel, rendered)
            elif step_type == "delay":
                seconds = max(0, min(float(step.get("seconds", 1)), 10))
                await asyncio.sleep(seconds)
            elif step_type == "react":
                emoji = str(step.get("emoji", "✅"))
                try:
                    await message.add_reaction(emoji)
                except Exception:
                    pass
            elif step_type == "internal":
                internal_name = str(step.get("action", "")).strip()
                params = step.get("params", {})
                if not isinstance(params, dict):
                    params = {}
                result = await self.execute_internal_action(
                    internal_name, params, message
                )
                assistant_notes.append(str(result))

        if assistant_notes:
            self.record_memory(
                message, "assistant", "\n".join(assistant_notes)[:2000]
            )
        return last_msg

    async def answer_from_brain(self, message: discord.Message, content: str) -> bool:
        knowledge = self.match_rule(content, self.knowledge_cache)
        if knowledge:
            rendered = self.render_text(knowledge["response_text"], message)
            await self.send_smart_message(message.channel, rendered, reply_to=message)
            self.record_memory(message, "assistant", rendered)
            self.mark_rule_used("learned_responses", "trigger", knowledge["trigger"])
            return True

        action = self.match_rule(content, self.actions_cache)
        if action:
            await self.execute_action(action, message)
            self.mark_rule_used("bot_actions", "action_name", action["action_name"])
            return True

        return False

    @quyen_group.command(name="add_admin", description="Thêm một người vào danh sách Admin bot")
    @app_commands.check(check_quyen)
    async def add_admin(self, interaction: discord.Interaction, member: discord.Member):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO admins VALUES (?)", (member.id,))
            conn.commit()
        await interaction.response.send_message(
            f"✅ Đã cấp quyền Admin bot cho {member.mention}",
            ephemeral=True,
        )

    @quyen_group.command(name="remove_admin", description="Xóa một người khỏi danh sách Admin bot")
    @app_commands.check(check_quyen)
    async def remove_admin(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        if member.id == ROOT_ADMIN:
            await interaction.response.send_message(
                "❌ Không thể xóa Root Admin!",
                ephemeral=True,
            )
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM admins WHERE user_id = ?", (member.id,))
            conn.commit()
        await interaction.response.send_message(
            f"🗑️ Đã thu hồi quyền Admin bot của {member.mention}",
            ephemeral=True,
        )

    @quyen_group.command(name="add_role", description="Cho phép một Role được dùng bot")
    @app_commands.check(check_quyen)
    async def add_role(self, interaction: discord.Interaction, role: discord.Role):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO roles VALUES (?)", (role.id,))
            conn.commit()
        await interaction.response.send_message(
            f"✅ Những ai có role {role.mention} giờ đã có thể dùng bot.",
            ephemeral=True,
        )

    @quyen_group.command(name="remove_role", description="Xóa Role khỏi danh sách được phép")
    @app_commands.check(check_quyen)
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM roles WHERE role_id = ?", (role.id,))
            conn.commit()
        await interaction.response.send_message(
            f"🗑️ Đã tước quyền sử dụng bot của role {role.name}",
            ephemeral=True,
        )

    @chatbot_group.command(name="learn", description="Dạy bot một câu trả lời mới")
    @app_commands.describe(
        trigger="Câu lệnh / câu hỏi",
        response="Nội dung bot phải trả lời",
        priority="Số nhỏ sẽ ưu tiên hơn",
    )
    @app_commands.choices(
        match_type=[
            app_commands.Choice(name="exact", value="exact"),
            app_commands.Choice(name="contains", value="contains"),
            app_commands.Choice(name="fuzzy", value="fuzzy"),
        ]
    )
    @app_commands.check(check_quyen)
    async def chatbot_learn(
        self,
        interaction: discord.Interaction,
        trigger: str,
        response: str,
        match_type: app_commands.Choice[str],
        priority: app_commands.Range[int, 1, 999] = 100,
    ):
        trigger_clean = trigger.strip()
        response_clean = response.strip()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO learned_responses
                   (trigger, normalized_trigger, response_text, response_type, match_type, priority, enabled, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    trigger_clean,
                    normalize_text(trigger_clean),
                    response_clean,
                    infer_response_type(response_clean),
                    match_type.value,
                    priority,
                    interaction.user.id,
                ),
            )
            conn.commit()
        self.reload_brain()
        await interaction.response.send_message(
            f"🧠 Đã dạy bot thành công.\n- Trigger: `{trigger_clean}`\n- Match: `{match_type.value}`\n- Priority: `{priority}`",
            ephemeral=True,
        )

    @chatbot_group.command(name="forget", description="Xóa một kiến thức đã dạy")
    @app_commands.check(check_quyen)
    async def chatbot_forget(self, interaction: discord.Interaction, trigger: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                "DELETE FROM learned_responses WHERE trigger = ? OR normalized_trigger = ?",
                (trigger.strip(), normalize_text(trigger)),
            )
            conn.commit()
            deleted = c.rowcount
        self.reload_brain()
        if deleted:
            await interaction.response.send_message(
                f"🗑️ Đã quên trigger `{trigger}`",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ Không tìm thấy trigger `{trigger}`",
                ephemeral=True,
            )

    @chatbot_group.command(name="list", description="Xem các kiến thức bot đang có")
    @app_commands.check(check_quyen)
    async def chatbot_list(
        self, interaction: discord.Interaction, limit: app_commands.Range[int, 1, 25] = 10
    ):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """SELECT trigger, match_type, priority, usage_count
                   FROM learned_responses
                   WHERE enabled = 1
                   ORDER BY priority ASC, trigger ASC
                   LIMIT ?""",
                (limit,),
            )
            rows = c.fetchall()

        if not rows:
            await interaction.response.send_message(
                "📭 Bot chưa có kiến thức nào.",
                ephemeral=True,
            )
            return

        lines = [
            f"`{trigger}` | match={match_type} | priority={priority} | used={usage_count}"
            for trigger, match_type, priority, usage_count in rows
        ]
        await interaction.response.send_message(
            "**📚 Kiến thức hiện tại:**\n" + "\n".join(lines),
            ephemeral=True,
        )

    @chatbot_group.command(name="pending", description="Xem các câu bot chưa biết để dạy thêm")
    @app_commands.check(check_quyen)
    async def chatbot_pending(
        self, interaction: discord.Interaction, limit: app_commands.Range[int, 1, 20] = 10
    ):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """SELECT id, username, content, created_at
                   FROM learning_queue
                   WHERE status = 'pending'
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = c.fetchall()

        if not rows:
            await interaction.response.send_message(
                "✅ Không có câu hỏi tồn nào cần dạy thêm.",
                ephemeral=True,
            )
            return

        lines = [f"`#{row[0]}` - **{row[1]}**: {row[2][:120]}" for row in rows]
        await interaction.response.send_message(
            "**📝 Câu hỏi đang chờ dạy:**\n" + "\n".join(lines),
            ephemeral=True,
        )

    @chatbot_group.command(name="answer", description="Trả lời một câu đang nằm trong hàng chờ học")
    @app_commands.choices(
        match_type=[
            app_commands.Choice(name="exact", value="exact"),
            app_commands.Choice(name="contains", value="contains"),
            app_commands.Choice(name="fuzzy", value="fuzzy"),
        ]
    )
    @app_commands.check(check_quyen)
    async def chatbot_answer(
        self,
        interaction: discord.Interaction,
        question_id: int,
        response: str,
        match_type: app_commands.Choice[str],
    ):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute(
                """SELECT content FROM learning_queue
                   WHERE id = ? AND status = 'pending'""",
                (question_id,),
            )
            row = c.fetchone()
            if not row:
                await interaction.response.send_message(
                    f"❌ Không tìm thấy câu chờ có ID `{question_id}`",
                    ephemeral=True,
                )
                return

            trigger = row[0].strip()
            c.execute(
                """INSERT OR REPLACE INTO learned_responses
                   (trigger, normalized_trigger, response_text, response_type, match_type, priority, enabled, created_by)
                   VALUES (?, ?, ?, ?, ?, 100, 1, ?)""",
                (
                    trigger,
                    normalize_text(trigger),
                    response.strip(),
                    infer_response_type(response),
                    match_type.value,
                    interaction.user.id,
                ),
            )
            c.execute(
                "UPDATE learning_queue SET status = 'learned', note = ? WHERE id = ?",
                (f"answered_by={interaction.user.id}", question_id),
            )
            conn.commit()

        self.reload_brain()
        await interaction.response.send_message(
            f"🧠 Bot đã học xong câu `#{question_id}`",
            ephemeral=True,
        )

    @chatbot_group.command(name="add_action", description="Tạo hành động để bot tự thực hiện")
    @app_commands.describe(
        name="Tên action",
        trigger="Câu kích hoạt",
        payload="Text hoặc JSON sequence",
        priority="Số nhỏ sẽ ưu tiên hơn",
    )
    @app_commands.choices(
        action_type=[
            app_commands.Choice(name="message", value="message"),
            app_commands.Choice(name="sequence", value="sequence"),
            app_commands.Choice(name="internal", value="internal"),
        ],
        match_type=[
            app_commands.Choice(name="exact", value="exact"),
            app_commands.Choice(name="contains", value="contains"),
            app_commands.Choice(name="fuzzy", value="fuzzy"),
        ],
    )
    @app_commands.check(check_quyen)
    async def chatbot_add_action(
        self,
        interaction: discord.Interaction,
        name: str,
        trigger: str,
        action_type: app_commands.Choice[str],
        payload: str,
        match_type: app_commands.Choice[str],
        priority: app_commands.Range[int, 1, 999] = 100,
    ):
        if action_type.value == "sequence":
            try:
                raw = json.loads(payload)
                if not isinstance(raw, list):
                    raise ValueError("JSON phải là array")
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Payload sequence không hợp lệ: {e}",
                    ephemeral=True,
                )
                return

        if action_type.value == "internal":
            try:
                raw = json.loads(payload)
                if not isinstance(raw, dict):
                    raise ValueError("JSON phải là object")
                if not any(raw.get(key) for key in ("action", "name", "internal_action")):
                    raise ValueError("Thiếu field action/name/internal_action")
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Payload internal không hợp lệ. Ví dụ: `{{\"action\":\"raobai\",\"params\":{{\"target\":\"ALL\"}}}}`\nLỗi: {e}",
                    ephemeral=True,
                )
                return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO bot_actions
                   (action_name, trigger, normalized_trigger, action_type, payload, match_type, priority, enabled, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (
                    name.strip(),
                    trigger.strip(),
                    normalize_text(trigger),
                    action_type.value,
                    payload.strip(),
                    match_type.value,
                    priority,
                    interaction.user.id,
                ),
            )
            conn.commit()
        self.reload_brain()
        await interaction.response.send_message(
            f"⚙️ Đã tạo action `{name}` với trigger `{trigger}` và kiểu `{action_type.value}`",
            ephemeral=True,
        )

    @chatbot_group.command(name="del_action", description="Xóa action đã cấu hình")
    @app_commands.check(check_quyen)
    async def chatbot_del_action(self, interaction: discord.Interaction, name: str):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM bot_actions WHERE action_name = ?", (name.strip(),))
            conn.commit()
            deleted = c.rowcount
        self.reload_brain()
        if deleted:
            await interaction.response.send_message(
                f"🗑️ Đã xóa action `{name}`",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ Không tìm thấy action `{name}`",
                ephemeral=True,
            )

    @chatbot_group.command(name="run_action", description="Chạy thử một action đã cấu hình")
    @app_commands.check(check_quyen)
    async def chatbot_run_action(
        self,
        interaction: discord.Interaction,
        name: str,
        fake_content: str = "",
    ):
        action = next(
            (item for item in self.actions_cache if item["action_name"] == name.strip()),
            None,
        )
        if not action:
            await interaction.response.send_message(
                f"❌ Không tìm thấy action `{name}`",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"▶️ Đang chạy thử action `{name}`...",
            ephemeral=True,
        )

        class FakeMessage:
            def __init__(self, src_interaction: discord.Interaction, content: str):
                self.author = src_interaction.user
                self.channel = src_interaction.channel
                self.guild = src_interaction.guild
                self.content = content or action["trigger"]
                self.mentions = []

            async def reply(
                self,
                content: Optional[str] = None,
                mention_author: bool = False,
                embed: Optional[discord.Embed] = None,
            ):
                if embed is not None:
                    return await self.channel.send(content=content, embed=embed)
                return await self.channel.send(content)

            async def add_reaction(self, emoji: str):
                try:
                    original = await interaction.original_response()
                    await original.add_reaction(emoji)
                except Exception:
                    pass

        fake_message = FakeMessage(interaction, fake_content or action["trigger"])
        await self.execute_action(action, fake_message)

    @chatbot_group.command(name="stats", description="Thống kê mức độ thông minh hiện tại của bot")
    @app_commands.check(check_quyen)
    async def chatbot_stats(self, interaction: discord.Interaction):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM learned_responses WHERE enabled = 1")
            knowledge_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM bot_actions WHERE enabled = 1")
            action_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM learning_queue WHERE status = 'pending'")
            pending_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM conversation_memory")
            memory_count = c.fetchone()[0]

        public_mode = self.get_config("chatbot_public", "0") == "1"
        threshold = self.get_config("chatbot_fuzzy_threshold", "0.86")
        msg = (
            "**📊 Chatbot stats**\n"
            f"- Kiến thức đã học: **{knowledge_count}**\n"
            f"- Action đã cấu hình: **{action_count}**\n"
            f"- Câu chờ dạy: **{pending_count}**\n"
            f"- Bộ nhớ hội thoại lưu: **{memory_count}**\n"
            f"- Public mode: **{'BẬT' if public_mode else 'TẮT'}**\n"
            f"- Fuzzy threshold: **{threshold}**"
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @chatbot_group.command(name="public", description="Bật / tắt chế độ ai cũng dùng được chatbot")
    @app_commands.check(check_quyen)
    async def chatbot_public(self, interaction: discord.Interaction, enabled: bool):
        self.set_config("chatbot_public", "1" if enabled else "0")
        await interaction.response.send_message(
            f"🌍 Public mode đã {'BẬT' if enabled else 'TẮT'}.",
            ephemeral=True,
        )

    @chatbot_group.command(name="fuzzy", description="Chỉnh độ nhạy của nhận diện gần đúng")
    @app_commands.check(check_quyen)
    async def chatbot_fuzzy(
        self,
        interaction: discord.Interaction,
        threshold: app_commands.Range[float, 0.5, 0.99],
    ):
        self.set_config("chatbot_fuzzy_threshold", f"{threshold:.2f}")
        await interaction.response.send_message(
            f"🎯 Đã chỉnh fuzzy threshold = `{threshold:.2f}`",
            ephemeral=True,
        )

    @app_commands.command(name="set_svv", description="Thay đổi link Server VIP")
    @app_commands.describe(link_moi="Dán link SVV mới vào đây")
    @app_commands.check(check_quyen)
    async def set_svv(self, interaction: discord.Interaction, link_moi: str):
        self.set_config("svv_link", link_moi)
        await interaction.response.send_message(
            f"✅ Đã cập nhật link SVV mới:\n{link_moi}",
            ephemeral=True,
        )

    @app_commands.command(name="set_catshop", description="Thay đổi ảnh bảng giá Cat Shop")
    @app_commands.describe(link_anh="Dán link ảnh mới (dùng image2url) vào đây")
    @app_commands.check(check_quyen)
    async def set_catshop(self, interaction: discord.Interaction, link_anh: str):
        self.set_config("cat_shop_img", link_anh)
        self.reload_brain()
        await interaction.response.send_message(
            "✅ Đã cập nhật ảnh bảng giá Cat Shop mới thành công!",
            ephemeral=True,
        )

    @app_commands.command(name="set_qr_fallback", description="Thay đổi ảnh QR fallback cho chatbot")
    @app_commands.describe(link_anh="Dán link ảnh QR fallback mới")
    @app_commands.check(check_quyen)
    async def set_qr_fallback(
        self, interaction: discord.Interaction, link_anh: str
    ):
        self.set_config("qr_fallback_img", link_anh)
        await interaction.response.send_message(
            "✅ Đã cập nhật QR fallback.",
            ephemeral=True,
        )

    @app_commands.command(name="svv", description="Lấy link Server VIP hiện tại")
    @app_commands.check(check_quyen)
    async def svv(self, interaction: discord.Interaction):
        link_hien_tai = self.get_config("svv_link")
        await interaction.response.send_message(link_hien_tai, ephemeral=True)

    @app_commands.command(name="banggia", description="Bảng giá Cat's shop")
    async def banggia(self, interaction: discord.Interaction):
        anh_hien_tai = self.get_config("cat_shop_img")
        await interaction.response.send_message(anh_hien_tai)

    @app_commands.command(name="raobai", description="Mở menu chọn server để rao bài")
    @app_commands.check(check_quyen)
    async def raobai(self, interaction: discord.Interaction):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT guild_id, guild_name FROM raobai_channels")
            rows = c.fetchall()

        if not rows:
            await interaction.response.send_message(
                "❌ Chưa có server nào được cấu hình.",
                ephemeral=True,
            )
            return

        options = [discord.SelectOption(label="Gửi tất cả Server", value="ALL", emoji="🚀")]
        for g_id, g_name in rows[:24]:
            options.append(
                discord.SelectOption(label=g_name[:100], value=str(g_id), emoji="💎")
            )

        embed = discord.Embed(
            title="🛒 Menu Rao Bài Tự Động",
            description="Chào mừng! Vui lòng chọn một server từ menu bên dưới.",
            color=discord.Color.purple(),
        )

        current_cat_shop_img = self.get_config("cat_shop_img")
        view = RaobaiView(self.bot, self.db_path, current_cat_shop_img, options)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="config_raobai", description="Cấu hình rao bài bằng ID Server và ID Kênh")
    @app_commands.describe(server_id="Nhập ID Server", channel_id="Nhập ID Kênh")
    @app_commands.check(check_quyen)
    async def config_raobai(
        self,
        interaction: discord.Interaction,
        server_id: str,
        channel_id: str,
    ):
        try:
            s_id, c_id = int(server_id), int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ ID phải là số!", ephemeral=True)
            return

        guild = self.bot.get_guild(s_id)
        if not guild:
            await interaction.response.send_message(
                f"❌ Bot không có mặt trong Server: `{s_id}`",
                ephemeral=True,
            )
            return

        channel = guild.get_channel(c_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ Không tìm thấy kênh văn bản này!",
                ephemeral=True,
            )
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO raobai_channels VALUES (?, ?, ?)",
                (s_id, c_id, guild.name),
            )
            conn.commit()

        await interaction.response.send_message(
            f"✅ Đã lưu: **{guild.name}** - **{channel.name}**",
            ephemeral=True,
        )

    @app_commands.command(name="botmessage", description="Gửi tin nhắn qua bot")
    @app_commands.check(check_quyen)
    async def botmessage(
        self,
        interaction: discord.Interaction,
        noidung: str = None,
        hinhanh: discord.Attachment = None,
    ):
        await interaction.response.send_message("ok", ephemeral=True)
        file = await hinhanh.to_file() if hinhanh else None
        await interaction.channel.send(content=noidung, file=file)

    @app_commands.command(name="beequipthatlac", description="Beequip thất lạc")
    async def beequipthatlac(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Beequip thất lạc của bố, thằng nào lấy thì cẩn thận"
        )
        await self.send_beequip(interaction.channel)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        self.record_memory(message, "user", message.content)

        public_mode = self.get_config("chatbot_public", "0") == "1"
        is_allowed = check_quyen(message.author)
        is_targeted = self.is_chatbot_target(message)

        if is_targeted and not public_mode and not is_allowed:
            await message.reply("im", delete_after=3.0, mention_author=False)
            await self.bot.process_commands(message)
            return

        if is_targeted:
            await self.handle_targeted_commands(message)
            await self.bot.process_commands(message)
            return

        content = self.strip_bot_prefix(message.content)

        if public_mode or is_allowed:
            if await self.answer_from_brain(message, content):
                await self.bot.process_commands(message)
                return

        await self.bot.process_commands(message)

    @raobai.error
    @config_raobai.error
    @botmessage.error
    @svv.error
    @set_svv.error
    @set_catshop.error
    @set_qr_fallback.error
    @add_admin.error
    @remove_admin.error
    @add_role.error
    @remove_role.error
    @chatbot_learn.error
    @chatbot_forget.error
    @chatbot_list.error
    @chatbot_pending.error
    @chatbot_answer.error
    @chatbot_add_action.error
    @chatbot_del_action.error
    @chatbot_run_action.error
    @chatbot_stats.error
    @chatbot_public.error
    @chatbot_fuzzy.error
    async def quyen_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"Down à mà dùng?\n*(ID: `{interaction.user.id}`)*",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Down à mà dùng?\n*(ID: `{interaction.user.id}`)*",
                    ephemeral=True,
                )
        else:
            text = f"❌ Có lỗi xảy ra: `{error}`"
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Chat(bot))