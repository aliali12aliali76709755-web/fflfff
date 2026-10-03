"""صانع بوتات: بوت مصنوع يعمل هو نفسه كصانع، ويسمح لمستخدميه بإنشاء بوتات من كل القوالب."""
from .. import maker as mk
from ..ctx import Ctx
from ..ui import B
from . import Tpl


class MakerTpl(Tpl):
    emoji, ar, en = "🏭", "صانع بوتات", "Bot maker"
    d_ar, d_en = "بوت صانع بوتات يسمح للمستخدمين بإنشاء بوتات من القوالب", "A bot maker that lets users create bots from the templates"
    cats = ("top",)
    guide_ar = ("بوتك يصبح صانع بوتات كاملاً باسمك: مستخدموه ينشئون بوتاتهم من كل القوالب ويديرونها من داخله.\n\n"
                "• إشعارات المستخدمين الجدد والبوتات الجديدة والبلاغات تصلك أنت.\n"
                "• البوتات التي ينشئها مستخدموك تعمل على نفس السيرفر.\n"
                "• اكتب /admin للعودة إلى لوحة المالك في أي وقت، واضغط «معاينة كمستخدم» لترى واجهة الصانع.")

    def setup(self, app) -> None:
        app.bot_data["maker_fid"] = app.bot_data["bot_id"]

    async def home(self, c: Ctx) -> None:
        await mk.ensure_user(mk.M(c.u, c.x))
        await mk.home(mk.M(c.u, c.x))

    async def owner(self, c: Ctx):
        from sqlalchemy import func, select

        from .. import db
        async with db.Session() as s:
            users = int((await s.execute(select(func.count()).select_from(db.MUser).where(db.MUser.factory_id == c.bot_id))).scalar() or 0)
            bots = int((await s.execute(select(func.count()).select_from(db.Bot).where(db.Bot.factory_id == c.bot_id))).scalar() or 0)
        return (c.t(f"👥 مستخدمو الصانع: {users}\n🤖 بوتات أُنشئت عبره: {bots}", f"👥 Maker users: {users}\n🤖 Bots created through it: {bots}"),
                [[B(c.t("🏭 فتح واجهة الصانع", "🏭 Open maker"), "m:home")]])

    async def start_param(self, c: Ctx, param: str) -> bool:
        if param.startswith(("ref_", "tr_", "bot_", "adm_")):
            await mk.on_start(c.u, c.x, param)
            return True
        return False

    async def cb(self, c: Ctx, a: list[str]) -> None:
        if a and a[0] == "m":
            await mk.on_callback(c.u, c.x)

    async def msg(self, c: Ctx) -> bool:
        return await mk.on_message(c.u, c.x)


TPL = MakerTpl()
