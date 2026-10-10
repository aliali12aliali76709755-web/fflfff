"""التعرف على الأغاني: المستخدم يرسل صوتاً أو فيديو، فيتعرف البوت على الأغنية.

يعمل عبر مكتبة shazamio المجانية المفتوحة (بلا مفتاح ولا حدود) باستخدام قاعدة
بيانات شازام العالمية. لا يحتاج القالب أي إعداد من صاحب البوت.
"""
from __future__ import annotations

import httpx

from .. import ui
from ..ctx import Ctx
from ..ui import B, esc, kb
from . import Tpl
from ._util import bump, cleanup, ffmpeg, grab


async def _recognize(sample_path) -> dict | None:
    from shazamio import Shazam  # استيراد مؤجل حتى لا يفشل الإقلاع إن لم تُثبّت

    data = await Shazam().recognize(str(sample_path))
    track = (data or {}).get("track")
    if not track:
        return None
    images = track.get("images") or {}
    cover = images.get("coverarthq") or images.get("coverart") or ""
    album = released = label = ""
    for sec in track.get("sections", []) or []:
        for meta in sec.get("metadata", []) or []:
            ttl = (meta.get("title") or "").lower()
            if ttl == "album":
                album = meta.get("text", "")
            elif ttl in ("released", "release date"):
                released = meta.get("text", "")
            elif ttl == "label":
                label = meta.get("text", "")
    genre = (track.get("genres") or {}).get("primary", "")
    preview = ""
    for action in (track.get("hub") or {}).get("actions", []) or []:
        uri = str(action.get("uri", ""))
        if action.get("type") == "uri" and uri.startswith("http"):
            preview = uri
            break
    return {
        "title": track.get("title", "?"), "artist": track.get("subtitle", "?"),
        "cover": cover, "album": album, "released": released, "label": label,
        "genre": genre, "preview": preview, "url": track.get("url", ""),
    }


class ShazamTpl(Tpl):
    emoji, ar, en = "🎵", "التعرف على الأغاني", "Song recognizer"
    d_ar, d_en = "تعرّف على أي أغنية من مقطع صوتي أو فيديو", "Identify any song from audio or video"
    guide_ar = (
        "المستخدم يرسل مقطعاً صوتياً أو فيديو أو رسالة صوتية فيها الأغنية، فيتعرف "
        "البوت عليها ويرسل اسمها واسم المغني وسنة الإصدار وصورة الغلاف ومقطعاً منها. "
        "لا يحتاج القالب أي إعداد، ويعمل عبر خدمة شازام المجانية."
    )
    guide_en = (
        "Users send audio, a video or a voice note; the bot identifies the song and "
        "replies with its title, artist, release year, cover art and a short preview. "
        "No setup required — powered by Shazam's free service."
    )

    async def home(self, c: Ctx) -> None:
        await c.edit(
            ui.head(c.brand) + "\n" + c.t(
                "🎧 أرسل مقطعاً صوتياً أو فيديو أو رسالة صوتية فيها الأغنية، وسأتعرف عليها فوراً.",
                "🎧 Send audio, a video or a voice note with the song and I'll identify it."),
            kb([c.tail()]))

    async def owner(self, c: Ctx):
        n = await c.kv("shz:count", 0)
        f = await c.kv("shz:found", 0)
        return c.t(f"🎵 عمليات البحث: {n} · تعرّف ناجح: {f}",
                   f"🎵 Searches: {n} · Found: {f}"), []

    async def msg(self, c: Ctx) -> bool:
        m = c.msg
        is_media = bool(
            m.audio or m.voice or m.video or m.video_note
            or (m.document and (m.document.mime_type or "").startswith(("audio", "video")))
        )
        if not is_media:
            if c.text:
                await c.send(c.t("🎧 أرسل مقطعاً صوتياً أو فيديو فيه الأغنية.",
                                 "🎧 Send audio or a video that contains the song."))
            return True

        src = await grab(c, ".media")
        if src is None:
            return True
        await bump(c, "shz:count")

        sample = c.tmp(".wav")
        # عينة 18 ثانية أحادية 44.1kHz مناسبة للتعرف
        ok, _ = await ffmpeg(["-t", "18", "-i", str(src), "-vn", "-ac", "1", "-ar", "44100", str(sample)])
        song = None
        if ok:
            try:
                song = await _recognize(sample)
            except Exception:
                song = None
        cleanup(src, sample)

        if not song:
            await c.send(c.t("😕 لم أتعرف على الأغنية. جرّب مقطعاً أوضح وفيه الغناء بصوت عالٍ.",
                             "😕 Couldn't identify it. Try a clearer clip with louder vocals."),
                         kb([c.home_row()]))
            return True

        await bump(c, "shz:found")
        cap = f"🎵 <b>{esc(song['title'])}</b>\n👤 {esc(song['artist'])}"
        if song["album"]:
            cap += c.t(f"\n💿 الألبوم: {esc(song['album'])}", f"\n💿 Album: {esc(song['album'])}")
        if song["released"]:
            cap += c.t(f"\n📅 الإصدار: {esc(song['released'])}", f"\n📅 Released: {esc(song['released'])}")
        if song["genre"]:
            cap += c.t(f"\n🎼 النوع: {esc(song['genre'])}", f"\n🎼 Genre: {esc(song['genre'])}")
        if song["label"]:
            cap += c.t(f"\n🏷️ الشركة: {esc(song['label'])}", f"\n🏷️ Label: {esc(song['label'])}")

        rows = []
        if song["url"]:
            rows.append([B(c.t("🔗 صفحة الأغنية", "🔗 Song page"), url=song["url"])])
        rows.append(c.home_row())

        sent = False
        if song["cover"]:
            try:
                await c.photo(song["cover"], caption=cap, kb=kb(rows))
                sent = True
            except Exception:
                sent = False
        if not sent:
            await c.send(cap, kb(rows))

        # مقطع صوتي قصير للأغنية إن توفّر
        if song["preview"]:
            p = c.tmp(".m4a")
            try:
                async with httpx.AsyncClient(timeout=40, follow_redirects=True) as cl:
                    r = await cl.get(song["preview"])
                if r.status_code == 200:
                    p.write_bytes(r.content)
                    await c.audio(str(p), title=song["title"], performer=song["artist"])
            except Exception:
                pass
            finally:
                cleanup(p)
        return True


TPL = ShazamTpl()
