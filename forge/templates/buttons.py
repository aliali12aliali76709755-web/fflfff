"""بوت الأزرار: شجرة أزرار مخصصة، كل زر يعرض محتوى وأزراراً فرعية."""
from telegram.error import TelegramError

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl

KEY = "buttons:tree"


class Buttons(Tpl):
    emoji, ar, en = "🔘", "بوت الأزرار", "Buttons bot"
    d_ar, d_en = "قوائم وأزرار تبنيها بنفسك، مع صفحة روابط على الويب", "Menus and buttons you build yourself, with a web links page"
    cats = ("top",)
    site = True
    guide_ar = ("ابنِ قوائمك بنفسك: كل زر له اسم ومحتوى (نص أو صورة/فيديو/ملف) وقد يحتوي أزراراً فرعية بلا حدود.\n\n"
                "1. اضغط «🛠 محرّر الأزرار».\n2. «➕ زر جديد» ثم أرسل اسمه.\n"
                "3. افتح الزر واضغط «📝 المحتوى» وأرسل ما يظهر عند الضغط عليه.\n4. أضف أزراراً فرعية داخل أي زر بنفس الطريقة.")

    async def tree(self, c: Ctx) -> list[dict]:
        return await c.kv(KEY, [])

    @staticmethod
    def kids(tree: list[dict], pid: int) -> list[dict]:
        return [n for n in tree if n["p"] == pid]

    async def home(self, c: Ctx) -> None:
        await self.view(c, 0)

    async def start_param(self, c: Ctx, param: str) -> bool:
        """رابط من صفحة الويب يفتح زراً بعينه: v<رقم الزر>."""
        if param.startswith("v") and param[1:].isdigit():
            await self.view(c, int(param[1:]))
            return True
        return False

    async def checklist(self, c: Ctx) -> list:
        tree = await self.tree(c)
        return [(bool(tree), c.t("أنشئ أول زر", "Create your first button"), "t:e:0"),
                (any(n.get("text") or n.get("src") for n in tree), c.t("أضف محتوى لزر واحد على الأقل", "Add content to at least one button"), "t:e:0"),
                (bool(await c.kv("buttons:home")), c.t("اكتب نص الصفحة الرئيسية", "Write the home page text"), "t:hm")]

    async def view(self, c: Ctx, nid: int) -> None:
        tree = await self.tree(c)
        node = next((n for n in tree if n["id"] == nid), None)
        if nid and node is None:
            nid = 0
        rows = ui.grid([B(n["t"], f"t:v:{n['id']}") for n in self.kids(tree, nid)], 2)
        if node is not None:
            rows.append([B(c.t("⬅️ رجوع", "⬅️ Back"), f"t:v:{node['p']}")])
        if c.is_owner:
            rows.append([B(c.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")])
        if node is None:
            text = await c.kv("buttons:home") or c.t("👋 أهلاً بك! اختر من الأزرار:", "👋 Welcome! Pick a button:")
            await c.edit(text, kb(rows))
            return
        if node.get("src"):
            try:
                await c.copy_to(c.chat.id, node["src"][0], node["src"][1], kb(rows))
                return
            except TelegramError:
                pass
        await c.edit(node.get("text") or f"<b>{esc(node['t'])}</b>", kb(rows))

    async def owner(self, c: Ctx):
        tree = await self.tree(c)
        return (c.t(f"🔘 عدد الأزرار: {len(tree)}", f"🔘 Buttons: {len(tree)}"),
                [[B(c.t("🛠 محرّر الأزرار", "🛠 Button editor"), "t:e:0")], [B(c.t("✏️ نص الصفحة الرئيسية", "✏️ Home text"), "t:hm")]])

    async def editor(self, c: Ctx, nid: int) -> None:
        tree = await self.tree(c)
        node = next((n for n in tree if n["id"] == nid), None)
        title = esc(node["t"]) if node else c.t("الصفحة الرئيسية", "Home page")
        has = c.t("✅ يوجد", "✅ set") if node and (node.get("text") or node.get("src")) else c.t("— فارغ", "— empty")
        text = ui.head(c.t("🛠 محرّر الأزرار", "🛠 Button editor")) + f"\n📍 {title}\n" + (
            c.t(f"📝 المحتوى: {has}\n", f"📝 Content: {has}\n") if node else "") + c.t("\nالأزرار داخل هذا المستوى:", "\nButtons at this level:")
        rows = ui.grid([B(f"📂 {n['t']}", f"t:e:{n['id']}") for n in self.kids(tree, nid if node else 0)], 2)
        rows.append([B(c.t("➕ زر جديد", "➕ New button"), f"t:add:{nid if node else 0}")])
        if node:
            rows.append([B(c.t("✏️ الاسم", "✏️ Rename"), f"t:ren:{nid}"), B(c.t("📝 المحتوى", "📝 Content"), f"t:con:{nid}")])
            rows.append([B(c.t("🗑 حذف الزر", "🗑 Delete"), f"t:del:{nid}", style="danger")])
            rows.append([B(c.t("⬅️ رجوع", "⬅️ Back"), f"t:e:{node['p']}")])
        else:
            rows.append([B(c.t("🎛 غرفة التحكم", "🎛 Control room"), "o:home")])
        await c.edit(text, kb(rows))

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act = a[0]
        if act == "v":
            await self.view(c, int(a[1]))
            return
        if not c.is_owner:
            return
        ask = {"add": c.t("✍️ أرسل اسم الزر الجديد.", "✍️ Send the new button's name."),
               "ren": c.t("✍️ أرسل الاسم الجديد.", "✍️ Send the new name."),
               "con": c.t("📝 أرسل المحتوى الذي يظهر عند ضغط الزر (نص أو صورة أو فيديو أو ملف).",
                          "📝 Send the content shown when the button is pressed (text, photo, video or file)."),
               "hm": c.t("✍️ أرسل نص الصفحة الرئيسية.", "✍️ Send the home page text.")}
        if act == "e":
            await self.editor(c, int(a[1]))
        elif act in ask:
            nid = int(a[1]) if len(a) > 1 else 0
            c.set_state("btn", act=act, id=nid)
            await c.edit(ask[act] + c.t("\n\n/cancel للإلغاء", "\n\n/cancel to abort"),
                         kb([[B(c.t("❌ إلغاء", "❌ Cancel"), f"t:e:{nid}")]]))
        elif act == "del":
            tree, nid = await self.tree(c), int(a[1])
            node = next((n for n in tree if n["id"] == nid), None)
            dead, grew = {nid}, True
            while grew:
                grew = False
                for n in tree:
                    if n["p"] in dead and n["id"] not in dead:
                        dead.add(n["id"])
                        grew = True
            await c.kv_set(KEY, [n for n in tree if n["id"] not in dead])
            await self.editor(c, node["p"] if node else 0)

    async def msg(self, c: Ctx) -> bool:
        st = c.st
        if not (c.is_owner and st and st["k"] == "btn"):
            await self.view(c, 0)
            return True
        tree, act, nid = await self.tree(c), st["act"], st["id"]
        c.clear_state()
        if act == "hm":
            await c.kv_set("buttons:home", c.msg.text_html or "")
            await c.send(c.t("✅ تم الحفظ.", "✅ Saved."), kb([c.home_row()]))
            return True
        if act == "add":
            new = {"id": max([n["id"] for n in tree], default=0) + 1, "p": nid, "t": (c.text or "زر")[:40]}
            tree.append(new)
            nid = new["id"]
        else:
            node = next((n for n in tree if n["id"] == nid), None)
            if node is None:
                return True
            if act == "ren":
                node["t"] = (c.text or node["t"])[:40]
            elif c.msg.text:
                node["text"], node["src"] = c.msg.text_html, None
            else:
                node["src"], node["text"] = [c.chat.id, c.msg.message_id], ""
        await c.kv_set(KEY, tree)
        await c.send(c.t("✅ تم الحفظ.", "✅ Saved."))
        await self.editor(c, nid)
        return True


TPL = Buttons()
