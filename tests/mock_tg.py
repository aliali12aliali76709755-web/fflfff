"""خادم Bot API وهمي للاختبار: يستقبل نداءات البوتات ويسمح بحقن تحديثات (رسائل وضغطات أزرار)."""
from __future__ import annotations

import asyncio
import json
import re
import time
from html.parser import HTMLParser

from aiohttp import web


ALLOWED = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "code", "pre", "blockquote", "tg-emoji"}
BAD_LT = re.compile(r"<(?!/?(?:%s)(?:\s[^<>]*)?>)" % "|".join(sorted(ALLOWED, key=len, reverse=True)))
BAD_AMP = re.compile(r"&(?!(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)")


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack, self.err = [], ""

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.err = f"unbalanced </{tag}>"


def html_problem(text: str) -> str:
    """يحاكي تدقيق تيليجرام لوضع HTML: وسوم مسموحة ومتوازنة، بلا < أو & عارية."""
    m = BAD_LT.search(text)
    if m:
        return f"bad '<' near: {text[max(0, m.start() - 20):m.start() + 30]!r}"
    m = BAD_AMP.search(text)
    if m:
        return f"bare '&' near: {text[max(0, m.start() - 20):m.start() + 30]!r}"
    p = _Balance()
    p.feed(text)
    return p.err or (f"unclosed <{p.stack[-1]}>" if p.stack else "")


class MockTG:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.webhooks: dict[int, str] = {}
        self.queues: dict[str, asyncio.Queue] = {}
        self.calls: list[dict] = []
        self.invalid: set[str] = set()
        self.names: dict[int, str] = {}
        self.members: dict[tuple[int, int], str] = {}   # (chat_id, user_id) -> status
        self.chats: dict[object, dict] = {}
        self.files: dict[str, bytes] = {}
        self.caps: dict[int, dict] = {}                 # خصائص إضافية لـ getMe
        self.managed: dict[int, str] = {}
        self.descriptions: dict[int, str] = {}
        self.delivered = 0
        self.processed = 0
        self._mid = 1000
        self._uid = 1
        self._last_call = time.monotonic()
        self.runner: web.AppRunner | None = None
        self.port = 0

    # ── الخادم ──
    async def start(self) -> None:
        app = web.Application(client_max_size=200 * 1024 * 1024)
        app.router.add_route("*", "/bot{token}/{method}", self._handle)
        app.router.add_get("/file/bot{token}/{path:.*}", self._file)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}/bot"

    @property
    def file_base(self) -> str:
        return f"http://127.0.0.1:{self.port}/file/bot"

    def _me(self, token: str) -> dict:
        bid = int(token.split(":")[0])
        d = {"id": bid, "is_bot": True, "first_name": self.names.get(bid, f"Bot{bid}"),
             "username": f"b{bid}_bot", "can_join_groups": True, "can_read_all_group_messages": False,
             "supports_inline_queries": True}
        d.update(self.caps.get(bid, {}))
        return d

    def _msg(self, token: str, chat_id, **extra) -> dict:
        self._mid += 1
        chat_id = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
        return {"message_id": self._mid, "date": int(time.time()),
                "chat": {"id": chat_id if isinstance(chat_id, int) else -100, "type": "private" if isinstance(chat_id, int) and chat_id > 0 else "channel"},
                "from": self._me(token), **extra}

    async def _file(self, request: web.Request) -> web.Response:
        return web.Response(body=self.files.get(request.match_info["path"], b""))

    async def _handle(self, request: web.Request) -> web.Response:
        token, method = request.match_info["token"], request.match_info["method"]
        params: dict = {}
        if request.content_type == "application/json":
            params = await request.json()
        elif request.can_read_body:
            post = await request.post()
            for k, v in post.items():
                if isinstance(v, web.FileField):
                    data = v.file.read()
                    params[k] = {"_file": v.filename, "_size": len(data)}
                    self.files[f"up/{v.filename}"] = data
                else:
                    try:
                        params[k] = json.loads(v)
                    except (ValueError, TypeError):
                        params[k] = v
        if token in self.invalid or ":" not in token:
            return web.json_response({"ok": False, "error_code": 401, "description": "Unauthorized"}, status=401)
        if method == "getUpdates":
            q = self.queues.setdefault(token, asyncio.Queue())
            ups = []
            try:
                ups.append(await asyncio.wait_for(q.get(), timeout=0.3))
                while not q.empty():
                    ups.append(q.get_nowait())
            except asyncio.TimeoutError:
                pass
            self.delivered += len(ups)
            return web.json_response({"ok": True, "result": ups})
        self._last_call = time.monotonic()
        self.calls.append({"token": token, "method": method, "p": params, "bot": int(token.split(":")[0])})
        body = params.get("text") or params.get("caption") or ""
        if isinstance(body, str):
            if params.get("parse_mode") == "HTML" and (bad := html_problem(body)):
                self.problems.append(f"{method}: {bad}")
            if len(body) > (4096 if "text" in params else 1024):
                self.problems.append(f"{method}: too long ({len(body)}) {body[:60]!r}")
        for row in (params.get("reply_markup") or {}).get("inline_keyboard", []) if isinstance(params.get("reply_markup"), dict) else []:
            for b in row:
                if not str(b.get("text", "")).strip():
                    self.problems.append(f"{method}: empty button text")
                if len(str(b.get("callback_data", "")).encode()) > 64:
                    self.problems.append(f"{method}: callback_data too long {b['callback_data']!r}")
        return web.json_response({"ok": True, "result": self._result(token, method, params)})

    def _result(self, token: str, method: str, p: dict):  # noqa: C901
        if method == "getMe":
            return self._me(token)
        if method in ("sendMessage", "editMessageText"):
            m = self._msg(token, p.get("chat_id", 0), text=p.get("text", ""))
            if method == "editMessageText" and p.get("message_id"):
                m["message_id"] = int(p["message_id"])
            if p.get("reply_markup"):
                m["reply_markup"] = p["reply_markup"]
            return m
        if method in ("sendDocument", "sendPhoto", "sendVideo", "sendAudio", "sendVoice", "sendSticker", "sendAnimation"):
            kind = method[4:].lower()
            fobj = {"file_id": f"F{self._mid}", "file_unique_id": f"U{self._mid}", "file_size": 10}
            body = {"photo": [dict(fobj, width=10, height=10)]} if kind == "photo" else {kind: dict(fobj, **(
                {"width": 10, "height": 10, "duration": 1} if kind in ("video", "animation") else
                {"duration": 1} if kind in ("audio", "voice") else
                {"width": 512, "height": 512, "is_animated": False, "is_video": False, "type": "regular"} if kind == "sticker" else {}))}
            return self._msg(token, p.get("chat_id", 0), **body)
        if method == "copyMessage":
            self._mid += 1
            return {"message_id": self._mid}
        if method == "getChatMember":
            uid = int(p.get("user_id", 0))
            cid = p.get("chat_id")
            cid = int(cid) if str(cid).lstrip("-").isdigit() else self.chats.get(cid, {}).get("id", cid)
            status = self.members.get((cid, uid), "left")
            user = {"id": uid, "is_bot": False, "first_name": "U"}
            if status == "administrator":
                return {"status": status, "user": user, "can_be_edited": False, "is_anonymous": False, "can_manage_chat": True,
                        "can_delete_messages": True, "can_manage_video_chats": True, "can_restrict_members": True,
                        "can_promote_members": False, "can_change_info": True, "can_invite_users": True,
                        "can_post_stories": True, "can_edit_stories": True, "can_delete_stories": True}
            if status == "kicked":
                return {"status": status, "user": user, "until_date": 0}
            return {"status": status, "user": user}
        if method == "getChat":
            c = self.chats.get(p.get("chat_id"))
            if c is None:
                cid = p.get("chat_id")
                c = {"id": int(cid) if str(cid).lstrip("-").isdigit() else -1001, "type": "channel", "title": "Chan"}
            return dict(c, accent_color_id=0, max_reaction_count=0, accepted_gift_types={
                "unlimited_gifts": True, "limited_gifts": True, "unique_gifts": True, "premium_subscription": True,
                "gifts_from_channels": True})
        if method == "getFile":
            return {"file_id": p.get("file_id"), "file_unique_id": "u", "file_size": len(self.files.get(p.get("file_id"), b"")),
                    "file_path": p.get("file_id")}
        if method == "createChatInviteLink":
            return {"invite_link": "https://t.me/+inv" + str(self._mid), "creator": self._me(token), "creates_join_request": False,
                    "is_primary": False, "is_revoked": False}
        if method == "getWebhookInfo":
            return {"url": self.webhooks.get(int(token.split(":")[0]), ""), "has_custom_certificate": False, "pending_update_count": 0}
        if method == "getChatMemberCount":
            return 42
        bid = int(token.split(":")[0])
        if method == "getMyDescription":
            return {"description": self.descriptions.get(bid, "")}
        if method == "getMyShortDescription":
            return {"short_description": ""}
        if method == "setMyDescription":
            if not p.get("language_code"):
                self.descriptions[bid] = p.get("description", "")
            return True
        if method == "getUserProfilePhotos":
            return {"total_count": 0, "photos": []}
        if method == "getManagedBotToken":
            return self.managed.get(int(p.get("user_id", 0)), "")
        return True

    # ── حقن التحديثات ──
    def user(self, uid: int, name: str = "Ali", lang: str = "ar", username: str = "") -> dict:
        d = {"id": uid, "is_bot": False, "first_name": name, "language_code": lang}
        if username:
            d["username"] = username
        return d

    def _push(self, token: str, update: dict) -> None:
        self._uid += 1
        update["update_id"] = self._uid
        self.queues.setdefault(token, asyncio.Queue()).put_nowait(update)

    def message(self, token: str, user: dict, text: str | None = None, **extra) -> int:
        self._mid += 1
        msg = {"message_id": self._mid, "date": int(time.time()), "chat": {"id": user["id"], "type": "private", "first_name": user["first_name"]},
               "from": user}
        if text is not None:
            msg["text"] = text
            if text.startswith("/"):
                msg["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        msg.update(extra)
        self._push(token, {"message": msg})
        return self._mid

    def photo(self, fid: str, data: bytes) -> dict:
        self.files[fid] = data
        return {"photo": [{"file_id": fid, "file_unique_id": "u" + fid, "width": 100, "height": 100, "file_size": len(data)}]}

    def document(self, fid: str, data: bytes, name: str, mime: str) -> dict:
        self.files[fid] = data
        return {"document": {"file_id": fid, "file_unique_id": "u" + fid, "file_name": name, "mime_type": mime, "file_size": len(data)}}

    def video(self, fid: str, data: bytes) -> dict:
        self.files[fid] = data
        return {"video": {"file_id": fid, "file_unique_id": "u" + fid, "width": 64, "height": 64, "duration": 1, "file_size": len(data),
                          "file_name": "v.mp4", "mime_type": "video/mp4"}}

    def callback(self, token: str, user: dict, data: str, message_id: int = 0) -> None:
        self._push(token, {"callback_query": {
            "id": str(self._uid + 1), "from": user, "chat_instance": "ci", "data": data,
            "message": {"message_id": message_id or self._mid, "date": int(time.time()),
                        "chat": {"id": user["id"], "type": "private"}, "from": self._me(token), "text": "x"}}})

    def raw(self, token: str, update: dict) -> None:
        self._push(token, update)

    async def settle(self, quiet: float = 0.12, timeout: float = 30.0) -> None:
        """ينتظر حتى تُسلَّم كل التحديثات وتنتهي معالجتها."""
        end = time.monotonic() + timeout
        await asyncio.sleep(0.02)
        while time.monotonic() < end:
            busy = any(not q.empty() for q in self.queues.values()) or self.processed < self.delivered
            if not busy and time.monotonic() - self._last_call > quiet:
                return
            await asyncio.sleep(0.02)
        raise AssertionError("mock: updates were not processed in time")

    # ── قراءة النتائج ──
    def out(self, bot_id: int, methods=("sendMessage", "editMessageText")) -> list[dict]:
        return [c for c in self.calls if c["bot"] == bot_id and c["method"] in methods]

    def last(self, bot_id: int) -> dict:
        o = self.out(bot_id)
        assert o, f"no messages from bot {bot_id}"
        return o[-1]["p"]

    def text(self, bot_id: int) -> str:
        return self.last(bot_id).get("text", "")

    def buttons(self, bot_id: int) -> list[dict]:
        for c in reversed(self.out(bot_id)):
            rm = c["p"].get("reply_markup")
            if rm and rm.get("inline_keyboard"):
                return [b for row in rm["inline_keyboard"] for b in row]
        return []

    def find(self, bot_id: int, label: str) -> dict:
        for b in self.buttons(bot_id):
            if label in b["text"]:
                return b
        raise AssertionError(f"button «{label}» not found in {[b['text'] for b in self.buttons(bot_id)]}")

    async def say(self, token: str, user: dict, text: str | None = None, **extra) -> str:
        self.message(token, user, text, **extra)
        await self.settle()
        return self.text(int(token.split(":")[0]))

    async def press(self, token: str, user: dict, label: str) -> str:
        bot_id = int(token.split(":")[0])
        b = self.find(bot_id, label)
        assert "callback_data" in b, f"button «{label}» is not a callback button: {b}"
        self.callback(token, user, b["callback_data"])
        await self.settle()
        return self.text(bot_id)

    async def click(self, token: str, user: dict, data: str) -> str:
        self.callback(token, user, data)
        await self.settle()
        return self.text(int(token.split(":")[0]))
