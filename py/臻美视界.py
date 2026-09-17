# -*- coding: utf-8 -*-
"""
臻美视界 - OK影视 Python 点播源（优化版）
- 封面使用直链（兼容 5.16，避免 proxy 图全不显示）
- 播放解析 master m3u8 直出子流，加快起播
- Session 复用 + 精简请求
站点: https://ommjs4.xxsxlz.top
"""

import base64
import json
import re
import sys
from urllib.parse import quote, urljoin, urlparse

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
        self.media_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.HOST + "/",
            "Origin": self.HOST,
            "Accept": "*/*",
        }
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update(self.headers)
            self.session.verify = False
            # 连接复用，减少握手
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=8, pool_maxsize=16, max_retries=1
            )
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
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

    def _fetch(self, path, timeout=12):
        url = self.HOST + "/api" + path
        text = ""
        if self.session:
            try:
                r = self.session.get(url, timeout=timeout)
                if r.status_code == 200:
                    text = r.text
            except Exception:
                pass
        if not text:
            try:
                import urllib.request
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
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
        if plain:
            n = plain[-1] if isinstance(plain[-1], int) else ord(plain[-1])
            if 1 <= n <= 16:
                plain = plain[:-n]
        try:
            return json.loads(plain.decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _get_bytes(self, url, timeout=12):
        """拉取图片/媒体原始内容"""
        if self.session:
            try:
                r = self.session.get(
                    url, headers=self.media_headers, timeout=timeout, stream=False
                )
                if r.status_code == 200 and r.content:
                    return r.content, r.headers.get("Content-Type", "")
            except Exception:
                pass
        try:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.media_headers)
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                return body, ctype
        except Exception:
            return b"", ""

    def _get_text(self, url, timeout=10):
        body, _ = self._get_bytes(url, timeout=timeout)
        if not body:
            return ""
        return body.decode("utf-8", errors="replace")

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

    def _pic(self, url):
        """封面直链（5.16 等版本 proxy 图容易全挂，改直链）"""
        if not url:
            return ""
        url = str(url).strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            return url
        # 去掉无意义查询参数，部分播放器对 ?t= 不友好
        url = re.sub(r"[?&](t|v|token)=[^&]*", "", url)
        url = url.replace("?&", "?").rstrip("?&")
        # 已知图床备用域名（主域失败时部分环境可解析备用）
        # 仅做轻量替换，不改变路径
        replacements = {
            "://fqjpg11.top/": "://fqjpg11.top/",
            "://thjpg14.vip/": "://thjpg14.vip/",
            "://sl260908.top/": "://sl260908.top/",
            "://guzwiayz.com/": "://guzwiayz.com/",
        }
        for a, b in replacements.items():
            if a in url:
                url = url.replace(a, b, 1)
                break
        return url

    def _resolve_m3u8(self, url):
        """
        若是 master playlist，解析出第一条子流绝对地址，减少播放器跳转，加快起播。
        失败则返回原 url。
        """
        if not url or ".m3u8" not in url:
            return url
        try:
            text = self._get_text(url, timeout=8)
            if not text or "#EXTM3U" not in text:
                return url
            # 已是媒体列表（有 EXTINF）直接返回
            if "#EXTINF" in text:
                return url
            # 找第一条非注释的相对/绝对 m3u8
            base = url.rsplit("/", 1)[0] + "/"
            for line in text.splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if ".m3u8" in s or s.endswith("/index.m3u8") or "hls" in s.lower():
                    return urljoin(url, s)
                # 也接受无扩展名的子路径
                if not s.startswith("#"):
                    return urljoin(url, s)
        except Exception:
            pass
        return url

    def _vod(self, item):
        vid = str(item.get("id") or "")
        name = self._clean(item.get("title") or item.get("name") or vid)
        pic = item.get("cover_url") or item.get("pic") or ""
        remarks = ""
        if item.get("hits"):
            try:
                h = int(item["hits"])
                if h >= 10000:
                    remarks = "%.1fw" % (h / 10000.0)
                else:
                    remarks = str(h)
            except Exception:
                remarks = str(item["hits"])
        elif item.get("category"):
            remarks = str(item["category"])
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._pic(pic),
            "vod_remarks": remarks,
        }

    def _play_header(self):
        return json.dumps(self.media_headers, ensure_ascii=False)

    # ------------------------------------------------------------------
    #  六接口
    # ------------------------------------------------------------------

    def homeContent(self, filter):
        classes = [
            {"type_id": c["type_id"], "type_name": c["type_name"]}
            for c in self.CATEGORIES
        ]
        data = self._fetch(
            "/videos?category_id={}&page=1&ps=18".format(self.CATEGORIES[0]["type_id"])
        )
        videos = []
        if data and isinstance(data.get("data"), dict):
            lst = data["data"].get("list") or []
            videos = [self._vod(x) for x in lst if isinstance(x, dict)]
        return {"class": classes, "list": videos}

    def homeVideoContent(self):
        data = self._fetch(
            "/videos?category_id={}&page=1&ps=30".format(self.CATEGORIES[0]["type_id"])
        )
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
        data = self._fetch("/movie?id={}".format(vid), timeout=10)
        if not data or not isinstance(data.get("data"), dict):
            return {"list": []}
        info = data["data"].get("info") or {}
        if not info:
            return {"list": []}
        name = self._clean(info.get("title") or vid)
        pic = info.get("cover_url") or ""
        play_url = (info.get("play_url") or "").strip()
        cate = info.get("category") or ""
        remarks = ""
        if info.get("hits"):
            try:
                h = int(info["hits"])
                remarks = "%.1fw热度" % (h / 10000.0) if h >= 10000 else "%s热度" % h
            except Exception:
                remarks = cate
        else:
            remarks = cate
        play_from = "臻美视界"
        # 详情阶段尽量解析出最终可播地址，播放时少一次跳转
        if play_url and play_url.startswith("http"):
            final = self._resolve_m3u8(play_url)
            vod_play_url = "正片${}".format(final)
        else:
            vod_play_url = "正片${}".format(vid)
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._pic(pic),
            "vod_content": name,
            "vod_remarks": remarks,
            "type_name": cate,
            "vod_play_from": play_from,
            "vod_play_url": vod_play_url,
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        play = str(id or "")
        hdr = self._play_header()

        # 已是直链 → 再解析一次 master，尽量给播放器最终子流
        if play.startswith("http") and (".m3u8" in play or ".mp4" in play):
            final = self._resolve_m3u8(play) if ".m3u8" in play else play
            return {
                "parse": 0,
                "playUrl": "",
                "url": final,
                "header": hdr,
            }

        # 还是 vid，补一次详情
        data = self._fetch("/movie?id={}".format(play), timeout=10)
        url = ""
        if data and isinstance(data.get("data"), dict):
            info = data["data"].get("info") or {}
            url = (info.get("play_url") or "").strip()
        if url and url.startswith("http"):
            final = self._resolve_m3u8(url) if ".m3u8" in url else url
            return {
                "parse": 0,
                "playUrl": "",
                "url": final,
                "header": hdr,
            }
        return {"parse": 1, "playUrl": "", "url": play, "header": hdr}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            page = max(1, int(pg or 1))
        except Exception:
            page = 1
        for path in (
            "/videos?keywords={}&page={}&ps=24".format(quote(key), page),
            "/search?keyword={}&page={}&ps=24".format(quote(key), page),
            "/videos?category_id=2383&page={}&ps=50&keywords={}".format(
                page, quote(key)
            ),
        ):
            data = self._fetch(path)
            if data and isinstance(data.get("data"), dict):
                lst = data["data"].get("list") or []
                if lst:
                    videos = [self._vod(x) for x in lst if isinstance(x, dict)]
                    kw = key.lower()
                    filtered = [
                        v
                        for v in videos
                        if kw in (v.get("vod_name") or "").lower()
                    ]
                    return {
                        "list": filtered or videos,
                        "page": page,
                        "pagecount": page + 1,
                        "limit": 24,
                        "total": 9999,
                    }
        return {"list": []}

    def localProxy(self, param):
        """
        代理封面图，避免防盗链导致不显示。
        支持: type=img
        """
        try:
            if isinstance(param, dict):
                p = param
            else:
                p = {}
                s = str(param or "")
                if "?" in s:
                    s = s.split("?", 1)[-1]
                from urllib.parse import parse_qsl
                p = dict(parse_qsl(s))
            typ = (p.get("type") or p.get("do") or "").lower()
            url = p.get("url") or ""
            if url:
                from urllib.parse import unquote
                url = unquote(url)
            if not url.startswith("http"):
                return [404, "text/plain", b"not found"]
            if typ in ("img", "pic", "image", "py") or not typ:
                body, ctype = self._get_bytes(url, timeout=12)
                if not body:
                    return [404, "text/plain", b"empty"]
                if not ctype or "text" in ctype:
                    # 根据后缀猜
                    low = url.lower()
                    if ".png" in low:
                        ctype = "image/png"
                    elif ".webp" in low:
                        ctype = "image/webp"
                    elif ".gif" in low:
                        ctype = "image/gif"
                    else:
                        ctype = "image/jpeg"
                return [200, ctype, body]
        except Exception:
            pass
        return [200, "text/plain", b"ok"]
