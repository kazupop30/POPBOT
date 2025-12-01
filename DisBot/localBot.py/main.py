import discord
from discord.ext import commands
from discord import app_commands, ui
import datetime
import os

from myserver import server_on


REPORT_CHANNEL_ID = 1444517938123247690       # ช่อง report
POLICE_ALERT_CHANNEL_ID = 1444518085745709098  # ช่องแจ้งเตือน police

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

report_counter = 0  # ตัวนับ report

# ---------------- Modal สำหรับกรอกเหตุผล + ข้อมูลเพิ่มเติม ----------------
class ReportModal(ui.Modal):
    reason = ui.TextInput(label="เหตุผล", style=discord.TextStyle.paragraph, placeholder="อธิบายเหตุผล", required=True)
    extra_info = ui.TextInput(label="ข้อมูลเพิ่มเติม (optional)", style=discord.TextStyle.paragraph, required=False)

    def __init__(self, reported_member: discord.Member, reporter: discord.Member, report_type: str):
        super().__init__(title=f"รายงาน {reported_member.display_name}")
        self.reported_member = reported_member
        self.reporter = reporter
        self.report_type = report_type

    async def on_submit(self, interaction: discord.Interaction):
        global report_counter
        report_counter += 1
        report_id = report_counter

        embed = discord.Embed(
            title=f"📣 รายงานการกระทำผิด (Case #{report_id})",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.add_field(name="👤 ผู้ถูกรายงาน", value=self.reported_member.mention, inline=False)
        embed.add_field(name="📝 ผู้รายงาน", value=self.reporter.mention, inline=False)
        embed.add_field(name="⚠️ ประเภทการกระทำผิด", value=self.report_type, inline=False)
        embed.add_field(name="📄 เหตุผล", value=self.reason.value, inline=False)
        if self.extra_info.value:
            embed.add_field(name="🗂 ข้อมูลเพิ่มเติม", value=self.extra_info.value, inline=False)

        report_channel = bot.get_channel(REPORT_CHANNEL_ID)
        if report_channel:
            await report_channel.send(
                embed=embed,
                view=ReportConfirmView(
                    self.reported_member,
                    report_id,
                    reason=self.reason.value,
                    extra_info=self.extra_info.value
                )
            )

        # แจ้งเตือน role police ผ่าน DM
        guild = interaction.guild
        police_role = discord.utils.get(guild.roles, name="police")
        if police_role:
            for member in police_role.members:
                try:
                    await member.send(f"📣 มีรายงานใหม่ Case #{report_id} จาก {self.reporter.mention} สำหรับ {self.reported_member.mention}")
                except:
                    pass

        # ส่ง DM ไปผู้รายงานว่ารายงานสำเร็จ
        try:
            await self.reporter.send(f"✅ รายงาน Case #{report_id} ของ {self.reported_member.display_name} สำเร็จแล้ว!")
        except:
            pass

        await interaction.response.send_message(f"✅ รายงานถูกส่งไปยังทีมแอดมินเรียบร้อย! (Case #{report_id})", ephemeral=True)

# ---------------- View สำหรับ confirm และปุ่มขอดูเหตุผล ----------------
class ReportConfirmView(ui.View):
    def __init__(self, reported_member, report_id, reason=None, extra_info=None):
        super().__init__(timeout=None)
        self.reported_member = reported_member
        self.report_id = report_id
        self.reason = reason
        self.extra_info = extra_info

    @ui.button(label="ยืนยันและส่ง DM", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        police_role = discord.utils.get(interaction.guild.roles, name="police")
        if police_role not in interaction.user.roles:
            await interaction.response.send_message("❌ คุณไม่มีสิทธิ์กดปุ่มนี้", ephemeral=True)
            return
        try:
            await self.reported_member.send(
                f"📣 คุณถูกรายงานจาก {interaction.user.mention} ในเซิร์ฟเวอร์ {interaction.guild.name} (Case #{self.report_id})",
                view=RequestReasonView(interaction.user, self.report_id, self.reason, self.extra_info)
            )

            alert_channel = bot.get_channel(POLICE_ALERT_CHANNEL_ID)
            if alert_channel:
                await alert_channel.send(f"Case #{self.report_id}: {interaction.user.mention} ได้ทำการกดยืนยันแล้ว")

            button.disabled = True
            await interaction.message.edit(view=self)

            await interaction.response.send_message("✅ DM ส่งไปยังผู้ถูกรายงานเรียบร้อย!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ ไม่สามารถส่ง DM ไปยังผู้ถูกรายงานได้", ephemeral=True)

# ---------------- View สำหรับผู้ถูก report กดขอดูเหตุผล ----------------
class RequestReasonView(ui.View):
    def __init__(self, reporter: discord.Member, report_id: int, report_reason: str, extra_info: str):
        super().__init__(timeout=None)
        self.reporter = reporter
        self.report_id = report_id
        self.report_reason = report_reason
        self.extra_info = extra_info

    @ui.button(label="ขอดูเหตุผลการถูกรายงาน", style=discord.ButtonStyle.blurple)
    async def request_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            await self.reporter.send(
                f"📩 {interaction.user.mention} ขอทราบเหตุผลการรายงานของ Case #{self.report_id}\n"
                "กรุณากดปุ่มด้านล่างเพื่ออนุมัติ",
                view=ApproveReasonView(interaction.user, self.report_reason, self.extra_info, self.report_id)
            )
            await interaction.response.send_message("✅ ระบบได้ส่งคำขอไปยังผู้รายงานแล้ว", ephemeral=True)
        except:
            await interaction.response.send_message("❌ ไม่สามารถส่งคำขอไปยังผู้รายงานได้", ephemeral=True)

# ---------------- View สำหรับผู้รายงานกดอนุมัติ ----------------
class ApproveReasonView(ui.View):
    def __init__(self, reported_member: discord.Member, reason: str, extra_info: str, report_id: int):
        super().__init__(timeout=None)
        self.reported_member = reported_member
        self.reason = reason
        self.extra_info = extra_info
        self.report_id = report_id

    @ui.button(label="อนุมัติให้ดูเหตุผล", style=discord.ButtonStyle.green)
    async def approve_button(self, interaction: discord.Interaction, button: ui.Button):
        try:
            embed = discord.Embed(
                title=f"📄 รายละเอียดรายงาน Case #{self.report_id}",
                color=discord.Color.orange()
            )
            embed.add_field(name="📄 เหตุผล", value=self.reason, inline=False)
            if self.extra_info:
                embed.add_field(name="🗂 ข้อมูลเพิ่มเติม", value=self.extra_info, inline=False)

            await self.reported_member.send(embed=embed)
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message("✅ ส่งรายละเอียดไปยังผู้ถูกรายงานเรียบร้อย!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ ไม่สามารถส่ง DM ให้ผู้ถูกรายงานได้", ephemeral=True)

# ---------------- Dropdown สำหรับเลือกประเภทการกระทำผิด ----------------
class ReportTypeSelect(ui.Select):
    def __init__(self, reported_member: discord.Member, reporter: discord.Member):
        options = [
            discord.SelectOption(label="โกง / Cheating"),
            discord.SelectOption(label="รบกวน / Harassment"),
            discord.SelectOption(label="ละเมิดกฎ / Rule Violation"),
            discord.SelectOption(label="อื่น ๆ / Other")
        ]
        super().__init__(placeholder="เลือกประเภทการกระทำผิด", min_values=1, max_values=1, options=options)
        self.reported_member = reported_member
        self.reporter = reporter

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ReportModal(self.reported_member, self.reporter, self.values[0]))

# ---------------- Slash Command ----------------
@bot.tree.command(name="report", description="รายงานผู้กระทำผิด")
@app_commands.describe(user="เลือกผู้ที่จะรายงาน")
async def report_command(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ คุณไม่สามารถรายงานตัวเองได้!", ephemeral=True)
        return
    view = ui.View()
    view.add_item(ReportTypeSelect(user, interaction.user))
    await interaction.response.send_message("กรุณาเลือกประเภทการกระทำผิด:", view=view, ephemeral=True)

# ---------------- Bot Ready ----------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot online as {bot.user}")

server_on()

bot.run(os.getenv('TOKEN'))
