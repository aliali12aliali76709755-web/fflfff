"""أدوات PDF: دمج ملفات، استخراج النص، عرض المعلومات، واقتطاع صفحات."""
import asyncio
import io
import re

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump, chunks, cleanup, too_big


def _merge(paths: list[str], out: str) -> int:
    from pypdf import PdfWriter
    w = PdfWriter()
    for p in paths:
        w.append(p)
    w.write(out)
    n = len(w.pages)
    w.close()
    return n


def _text(path: str) -> str:
    from pypdf import PdfReader
    r = PdfReader(path)
    return "\n\n".join((pg.extract_text() or "").strip() for pg in r.pages[:200]).strip()


def _info(path: str) -> dict:
    from pypdf import PdfReader
    r = PdfReader(path)
    meta = r.metadata or {}
    return {"pages": len(r.pages), "title": meta.get("/Title") or "", "author": meta.get("/Author") or "",
            "creator": meta.get("/Creator") or meta.get("/Producer") or "", "enc": r.is_encrypted}


def _split(path: str, out: str, a: int, b: int) -> int:
    from pypdf import PdfReader, PdfWriter
    r, w = PdfReader(path), PdfWriter()
    for i in range(max(1, a) - 1, min(b, len(r.pages))):
        w.add_page(r.pages[i])
    w.write(out)
    return len(w.pages)


class PdfTools(Tpl):
    emoji, ar, en = "📑", "أدوات PDF", "PDF tools"
    d_ar, d_en = "ادمج PDFs، استخرج نصاً، اعرض المعلومات", "Merge PDFs, extract text, show info"
    cats = ("tools",)
    guide_ar = ("المستخدم يرسل ملف PDF أو أكثر ثم يختار:\n• 🔗 دمج كل الملفات المرسلة في ملف واحد بترتيب إرسالها.\n• 📝 استخراج النص (للملفات النصية لا الممسوحة ضوئياً).\n"
                "• ℹ️ عدد الصفحات والعنوان والمؤلف.\n• ✂️ اقتطاع صفحات محددة مثل 2-5.\n\nلا يحتاج القالب أي إعداد.")

    def files(self, c: Ctx) -> list[dict]:
        return c.x.user_data.setdefault("pdfs", [])

    def menu(self, c: Ctx):
        t, n = c.t, len(self.files(c))
        return kb([[B(t(f"🔗 دمج ({n})", f"🔗 Merge ({n})"), "t:merge")] if n > 1 else None,
                   [B(t("📝 استخراج النص", "📝 Extract text"), "t:text"), B(t("ℹ️ معلومات", "ℹ️ Info"), "t:info")],
                   [B(t("✂️ اقتطاع صفحات", "✂️ Extract pages"), "t:split"), B(t("🗑 مسح القائمة", "🗑 Clear list"), "t:clr")]])

    async def home(self, c: Ctx) -> None:
        self.files(c).clear()
        await c.edit(ui.head(c.brand) + "\n" + c.t("📎 أرسل ملف PDF (أو عدة ملفات للدمج).", "📎 Send a PDF file (or several to merge)."), kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("pdf:count", 0)
        return c.t(f"📑 عمليات PDF: {n}", f"📑 PDF operations: {n}"), []

    async def fetch(self, c: Ctx, items: list[dict]) -> list:
        return [await c.download(x["fid"], ".pdf") for x in items]

    async def cb(self, c: Ctx, a: list[str]) -> None:
        act, t, files = a[0], c.t, self.files(c)
        if act == "clr":
            await self.home(c)
            return
        if not files:
            await c.answer(t("أرسل ملف PDF أولاً.", "Send a PDF first."), True)
            return
        if act == "split":
            c.set_state("pdf_split")
            await c.send(t("✂️ أرسل نطاق الصفحات مثل <code>2-5</code> (من آخر ملف أرسلته).", "✂️ Send the page range like <code>2-5</code> (from the last file)."))
            return
        paths, out = [], None
        try:
            if act == "merge":
                paths, out = await self.fetch(c, files), c.tmp(".pdf")
                n = await asyncio.to_thread(_merge, [str(p) for p in paths], str(out))
                with open(out, "rb") as fh:
                    await c.doc(fh, filename="merged.pdf", caption=t(f"✅ دُمج {len(files)} ملفات في {n} صفحة.", f"✅ Merged {len(files)} files into {n} pages."))
                files.clear()
            elif act == "text":
                paths = await self.fetch(c, files[-1:])
                text = await asyncio.to_thread(_text, str(paths[0]))
                if not text:
                    await c.send(t("⚠️ لا يوجد نص قابل للاستخراج (ربما الملف صور ممسوحة).", "⚠️ No extractable text (the file may be scanned images)."))
                elif len(text) > 7000:
                    await c.doc(io.BytesIO(text.encode("utf-8")), filename="text.txt", caption=t("📝 النص المستخرج.", "📝 Extracted text."))
                else:
                    for part in chunks(text):
                        await c.send(esc(part))
            elif act == "info":
                paths = await self.fetch(c, files[-1:])
                i = await asyncio.to_thread(_info, str(paths[0]))
                await c.send(ui.head(f"ℹ️ {esc(files[-1]['name'])}") + ui.rows([
                    (t("الصفحات", "Pages"), i["pages"]), (t("العنوان", "Title"), i["title"] or "—"), (t("المؤلف", "Author"), i["author"] or "—"),
                    (t("البرنامج", "Creator"), i["creator"] or "—"), (t("مشفّر", "Encrypted"), t("نعم", "yes") if i["enc"] else t("لا", "no")),
                    (t("الحجم", "Size"), f"{files[-1]['size'] / 1048576:.2f}MB")]), self.menu(c))
            else:
                return
            await bump(c, "pdf:count")
        except Exception:
            await c.send(t("⚠️ تعذّرت معالجة الملف (قد يكون تالفاً أو محمياً بكلمة مرور).", "⚠️ Couldn't process the file (it may be damaged or password-protected)."))
        finally:
            cleanup(out, *paths)

    async def msg(self, c: Ctx) -> bool:
        st, t = c.st, c.t
        if st and st["k"] == "pdf_split":
            m = re.fullmatch(r"\s*(\d+)\s*[-–]\s*(\d+)\s*", c.text) or re.fullmatch(r"\s*(\d+)\s*", c.text)
            files = self.files(c)
            if not m or not files:
                await c.send(t("⚠️ مثال صحيح: <code>2-5</code>", "⚠️ Valid example: <code>2-5</code>"))
                return True
            c.clear_state()
            a, b = int(m.group(1)), int(m.group(m.lastindex))
            src = out = None
            try:
                src, out = await c.download(files[-1]["fid"], ".pdf"), c.tmp(".pdf")
                n = await asyncio.to_thread(_split, str(src), str(out), min(a, b), max(a, b))
                if not n:
                    await c.send(t("⚠️ النطاق خارج صفحات الملف.", "⚠️ Range is outside the file's pages."))
                    return True
                with open(out, "rb") as fh:
                    await c.doc(fh, filename=f"pages_{a}-{b}.pdf", caption=t(f"✅ {n} صفحة.", f"✅ {n} pages."))
                await bump(c, "pdf:count")
            except Exception:
                await c.send(t("⚠️ تعذّرت معالجة الملف.", "⚠️ Couldn't process the file."))
            finally:
                cleanup(src, out)
            return True
        d = c.msg.document
        if d is None or not ((d.mime_type or "") == "application/pdf" or (d.file_name or "").lower().endswith(".pdf")):
            await c.send(t("📎 أرسل ملفاً بصيغة PDF.", "📎 Please send a PDF file."))
            return True
        err = too_big(c, d.file_size or 0)
        if err:
            await c.send(err)
            return True
        files = self.files(c)
        files.append({"fid": d.file_id, "name": d.file_name or "file.pdf", "size": d.file_size or 0})
        del files[:-20]
        await c.send(t(f"📥 استلمت: {esc(d.file_name or 'file.pdf')}\nالملفات في القائمة: {len(files)}\n\nأرسل ملفاً آخر للدمج، أو اختر عملية:",
                       f"📥 Got: {esc(d.file_name or 'file.pdf')}\nFiles in list: {len(files)}\n\nSend another to merge, or pick an action:"), self.menu(c))
        return True


TPL = PdfTools()
