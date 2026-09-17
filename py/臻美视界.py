# -*- coding: utf-8 -*-
"""
臻美视界 - OK影视 Python 点播源
原 Cloudflare Worker 逻辑移植
站点: https://ommjs4.xxsxlz.top
API 响应 AES-CBC 解密 (key/iv 固定)
"""

import base64
import json
import re
import sys
from urllib.parse import quote

sys.path.append("..")
try:
    from base.spider import Spider
except Exception:
    class Spider:
        def init(self, extend=""):
            pass


class Spider(Spider):

    HOST = "https://ommjs4.xxsxlz.top"
    API_KEY = b"a9yX32LpQvUt7wBc"
    API_IV = b"N7cPk2Bv38hWqFzM"

    CATEGORIES = [
        {"type_id": "2383", "type_name": "乱伦毁三观"},
        {"type_id": "2411", "type_name": "中文字幕"},
        {"type_id": "2412", "type_name": "SM调教"},
        {"type_id": "2421", "type_name": "丝袜制服"},
        {"type_id": "2432", "type_name": "国内换脸"},
        {"type_id": "2433", "type_name": "自拍偷拍"},
        {"type_id": "2434", "type_name": "传媒剧情"},
        {"type_id": "2435", "type_name": "抖阴短片"},
        {"type_id": "2436", "type_name": "网爆吃瓜"},
        {"type_id": "2437", "type_name": "偷拍偷窥"},
        {"type_id": "2438", "type_name": "探花约炮"},
        {"type_id": "2439", "type_name": "主播诱惑"},
        {"type_id": "2440", "type_name": "国产自拍"},
        {"type_id": "2441", "type_name": "女优明星"},
        {"type_id": "2443", "type_name": "日韩无码"},
        {"type_id": "2444", "type_name": "日韩精品"},
    ]

    def init(self, extend=""):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": self.HOST + "/",
            "Accept": "application/json,text/html,*/*",
            "Origin": self.HOST,
        }
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            self.session.verify = False
        except Exception:
            self.session = None

    def getName(self):
        return "臻美视界"

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in url or ".mp4" in url))

    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------------
    #  内部工具
    # ------------------------------------------------------------------

    def _fetch(self, path):
        url = self.HOST + "/api" + path
        text = ""
        if self.session:
            try:
                r = self.session.get(url, timeout=15)
                if r.status_code == 200:
                    text = r.text
            except Exception:
                pass
        if not text:
            try:
                import urllib.request, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
            except Exception:
                return None
        if not text:
            return None
        try:
            obj = json.loads(text)
        except Exception:
            return None
        if isinstance(obj, dict) and obj.get("cipher"):
            return self._decrypt(obj["cipher"])
        return obj

    def _decrypt(self, cipher_b64):
        try:
            raw = base64.b64decode(cipher_b64)
        except Exception:
            return None
        plain = None
        # 优先 cryptography
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            dec = Cipher(
                algorithms.AES(self.API_KEY),
                modes.CBC(self.API_IV),
                backend=default_backend(),
            ).decryptor()
            plain = dec.update(raw) + dec.finalize()
        except Exception:
            pass
        if plain is None:
            try:
                from Crypto.Cipher import AES
                plain = AES.new(self.API_KEY, AES.MODE_CBC, self.API_IV).decrypt(raw)
            except Exception:
                return None
        # PKCS7 unpad
        if plain:
            n = plain[-1] if isinstance(plain[-1], int) else ord(plain[-1])
            if 1 <= n <= 16:
                plain = plain[:-n]
        try:
            return json.loads(plain.decode("utf-8", errors="replace"))
        except Exception:
            return None

    @staticmethod
    def _clean(text):
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", str(text))
        text = (
            text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&nbsp;", " ")
        )
        return re.sub(r"\s+", " ", text).strip()

    def _vod(self, item):
        vid = str(item.get("id") or "")
        name = self._clean(item.get("title") or item.get("name") or vid)
        pic = item.get("cover_url") or item.get("pic") or ""
        remarks = ""
        if item.get("hits"):
            remarks = "热度{}".format(item["hits"])
        elif item.get("category"):
            remarks = str(item["category"])
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
        }

    # ------------------------------------------------------------------
    #  六接口
    # ------------------------------------------------------------------

    def homeContent(self, filter):
        classes = [
            {"type_id": c["type_id"], "type_name": c["type_name"]}
            for c in self.CATEGORIES
        ]
        # 首页取第一个分类前几条做推荐
        data = self._fetch("/videos?category_id={}&page=1&ps=18".format(self.CATEGORIES[0]["type_id"]))
        videos = []
        if data and isinstance(data.get("data"), dict):
            lst = data["data"].get("list") or []
            videos = [self._vod(x) for x in lst if isinstance(x, dict)]
        return {"class": classes, "list": videos}

    def homeVideoContent(self):
        data = self._fetch("/videos?category_id={}&page=1&ps=30".format(self.CATEGORIES[0]["type_id"]))
        videos = []
        if data and isinstance(data.get("data"), dict):
            lst = data["data"].get("list") or []
            videos = [self._vod(x) for x in lst if isinstance(x, dict)]
        return {"list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        ps = 24
        path = "/videos?category_id={}&page={}&ps={}".format(tid, page, ps)
        data = self._fetch(path)
        videos = []
        total = 0
        pagecount = page
        if data and isinstance(data.get("data"), dict):
            d = data["data"]
            lst = d.get("list") or []
            videos = [self._vod(x) for x in lst if isinstance(x, dict)]
            total = int(d.get("total") or 0)
            pages = int(d.get("pages") or 0)
            if pages > 0:
                pagecount = pages
            elif total > 0:
                pagecount = max(1, (total + ps - 1) // ps)
        return {
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": ps,
            "total": total or (pagecount * ps),
            "list": videos,
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        data = self._fetch("/movie?id={}".format(vid))
        if not data or not isinstance(data.get("data"), dict):
            return {"list": []}
        info = data["data"].get("info") or {}
        if not info:
            return {"list": []}
        name = self._clean(info.get("title") or vid)
        pic = info.get("cover_url") or ""
        play_url = (info.get("play_url") or "").strip()
        cate = info.get("category") or ""
        remarks = "热度{}".format(info["hits"]) if info.get("hits") else cate
        # 单集直链
        play_from = "臻美视界"
        if play_url and play_url.startswith("http"):
            vod_play_url = "正片${}".format(play_url)
        else:
            # 兜底：播放时再解析
            vod_play_url = "正片${}".format(vid)
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": name,
            "vod_remarks": remarks,
            "type_name": cate,
            "vod_play_from": play_from,
            "vod_play_url": vod_play_url,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        play = str(id or "")
        # 已经是直链
        if play.startswith("http") and (".m3u8" in play or ".mp4" in play):
            return {
                "parse": 0,
                "playUrl": "",
                "url": play,
                "header": json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.HOST + "/",
                }),
            }
        # 用 id 再请求一次
        data = self._fetch("/movie?id={}".format(play))
        url = ""
        if data and isinstance(data.get("data"), dict):
            info = data["data"].get("info") or {}
            url = (info.get("play_url") or "").strip()
        if url and url.startswith("http"):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.HOST + "/",
                }),
            }
        return {"parse": 1, "playUrl": "", "url": play}

    def searchContent(self, key, quick=False, pg="1"):
        # 原站搜索接口未在 Worker 中暴露，这里用第一个分类 + 关键词过滤做简单兼容
        # 若站点后续有 search API 可再扩展
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        # 尝试常见搜索路径
        for path in (
            "/videos?keywords={}&page={}&ps=24".format(quote(key), page),
            "/search?keyword={}&page={}&ps=24".format(quote(key), page),
            "/videos?category_id=2383&page={}&ps=50&keywords={}".format(page, quote(key)),
        ):
            data = self._fetch(path)
            if data and isinstance(data.get("data"), dict):
                lst = data["data"].get("list") or []
                if lst:
                    videos = [self._vod(x) for x in lst if isinstance(x, dict)]
                    # 本地再滤一遍标题
                    kw = key.lower()
                    videos = [v for v in videos if kw in (v.get("vod_name") or "").lower()] or videos
                    return {"list": videos, "page": page, "pagecount": page + 1, "limit": 24, "total": 9999}
        return {"list": []}

    def localProxy(self, param):
        return [200, "text/plain", b"ok"]
