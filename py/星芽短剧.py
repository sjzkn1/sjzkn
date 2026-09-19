# -*- coding: utf-8 -*-
"""
星芽短剧 - OK影视 Python 点播源（优化版）
- Token 缓存，避免每次请求登录
- Session 连接复用
- 全部分类（主分类 + 剧场子分类）
- 去掉外部跳转依赖，加快详情加载
"""

from __future__ import annotations

import base64
import json
import sys
import time

import requests

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def init(self, extend=""):
            pass

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
except Exception:
    AES = None
    pad = None


class Spider(BaseSpider):
    host = "https://app.whjzjx.cn"
    login_url = "https://u.shytkjgs.com/user/v3/account/login"
    aes_key = b"B@ecf920Od8A4df7"
    UA = (
        "Mozilla/5.0 (Linux; Android 12; Pixel 3 XL) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/98.0.4758.101 Mobile Safari/537.36"
    )

    # 模块级缓存（多实例共享）
    _token = ""
    _token_ts = 0
    _token_ttl = 6 * 3600
    _classes_cache = None
    _classes_ts = 0

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.UA,
                "platform": "1",
                "version_name": "3.8.3.1",
                "Accept": "application/json",
            }
        )
        self.session.verify = False
        try:
            from requests.adapters import HTTPAdapter

            ad = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=1)
            self.session.mount("https://", ad)
            self.session.mount("http://", ad)
        except Exception:
            pass
        # 预热 token
        try:
            self._ensure_token()
        except Exception:
            pass

    def getName(self):
        return "星芽短剧"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    # ---------- auth ----------
    def _ensure_token(self):
        now = time.time()
        if Spider._token and (now - Spider._token_ts) < Spider._token_ttl:
            return Spider._token
        if AES is None or pad is None:
            raise RuntimeError("缺少 pycryptodome，无法登录星芽")
        payload = {
            "device": "2a50580e69d38388c94c93605241fb306",
            "package_name": "com.jz.xydj",
            "android_id": "ec1280db12795506",
            "install_first_open": True,
            "first_install_time": 1752505243345,
            "last_update_time": 1752505243345,
            "report_link_url": "",
            "authorization": "",
            "timestamp": int(time.time() * 1000),
        }
        plain = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        cipher = AES.new(self.aes_key, AES.MODE_ECB)
        encrypted = base64.b64encode(cipher.encrypt(pad(plain, 16))).decode("utf-8")
        headers = {
            "platform": "1",
            "user_agent": self.UA,
            "content-type": "application/json; charset=utf-8",
        }
        r = self.session.post(self.login_url, headers=headers, data=encrypted, timeout=12)
        r.raise_for_status()
        data = r.json()
        token = ((data.get("data") or {}).get("token")) or ""
        if not token:
            raise RuntimeError("星芽登录失败")
        Spider._token = token
        Spider._token_ts = now
        return token

    def _headers(self):
        token = self._ensure_token()
        return {
            "authorization": token,
            "platform": "1",
            "version_name": "3.8.3.1",
            "User-Agent": self.UA,
            "Accept": "application/json",
        }

    def _get(self, path, params=None, timeout=12):
        url = path if path.startswith("http") else (self.host + path)
        try:
            r = self.session.get(url, headers=self._headers(), params=params, timeout=timeout)
            if r.status_code == 401:
                Spider._token = ""
                r = self.session.get(url, headers=self._headers(), params=params, timeout=timeout)
            if r.status_code != 200:
                return {}
            return r.json()
        except Exception:
            return {}

    def _post(self, path, body=None, timeout=12):
        url = path if path.startswith("http") else (self.host + path)
        try:
            r = self.session.post(url, headers=self._headers(), json=body or {}, timeout=timeout)
            if r.status_code == 401:
                Spider._token = ""
                r = self.session.post(url, headers=self._headers(), json=body or {}, timeout=timeout)
            if r.status_code != 200:
                return {}
            return r.json()
        except Exception:
            return {}

    # ---------- classes ----------
    def _load_classes(self):
        now = time.time()
        if Spider._classes_cache and (now - Spider._classes_ts) < 3600:
            return Spider._classes_cache
        data = self._get("/v1/theater/classes")
        rows = ((data.get("data") or {}).get("list")) or []
        main = []
        filters = {}
        for row in rows:
            cid = str(row.get("id") or "")
            name = str(row.get("class_name") or "").strip()
            if not cid or not name:
                continue
            main.append({"type_id": cid, "type_name": name})
            subs = row.get("general_class") or []
            if subs:
                values = [{"n": "全部", "v": ""}]
                for s in subs:
                    sid = str(s.get("id") or "")
                    sname = str(s.get("class_name") or "").strip()
                    if sid and sname:
                        values.append({"n": sname, "v": sid})
                if len(values) > 1:
                    filters[cid] = [{"key": "class2_id", "name": "类型", "value": values}]
        # 没有拉到时兜底
        if not main:
            main = [
                {"type_id": "1", "type_name": "剧场"},
                {"type_id": "3", "type_name": "新剧"},
                {"type_id": "2", "type_name": "热播剧"},
                {"type_id": "7", "type_name": "星选好剧"},
                {"type_id": "5", "type_name": "阳光剧场"},
                {"type_id": "9", "type_name": "排行榜"},
            ]
        Spider._classes_cache = {"class": main, "filters": filters}
        Spider._classes_ts = now
        return Spider._classes_cache

    def homeContent(self, filter):
        data = self._load_classes()
        return {
            "class": data["class"],
            "filters": data.get("filters") or {},
            "filterable": 1 if data.get("filters") else 0,
        }

    def homeVideoContent(self):
        data = self._get(
            "/v1/theater/home_page",
            params={
                "theater_class_id": "1",
                "class2_id": "4",
                "page_num": "1",
                "page_size": "24",
            },
        )
        return {"list": self._parse_list(data)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or 1)
        tid = str(tid or "1")
        params = {
            "theater_class_id": tid,
            "page_num": pg,
            "page_size": "24",
        }
        if isinstance(extend, dict):
            c2 = extend.get("class2_id")
            if c2 not in (None, "", "0", "all"):
                params["class2_id"] = str(c2)
        data = self._get("/v1/theater/home_page", params=params)
        videos = self._parse_list(data)
        # 粗略分页
        total = ((data.get("data") or {}).get("total")) or 0
        try:
            total = int(total)
        except Exception:
            total = len(videos)
        pagecount = max(1, (total + 23) // 24) if total else (int(pg) + (1 if len(videos) >= 24 else 0))
        return {
            "list": videos,
            "page": int(pg),
            "pagecount": max(pagecount, int(pg)),
            "limit": 24,
            "total": total or len(videos),
        }

    def detailContent(self, ids):
        did = str(ids[0] if isinstance(ids, list) else ids)
        data = self._get("/v2/theater_parent/detail", params={"theater_parent_id": did})
        payload = data.get("data") or {}
        if not payload:
            return {"list": []}

        title = str(payload.get("title") or f"短剧{did}")
        pic = str(payload.get("cover_url") or "")
        intro = str(payload.get("introduction") or payload.get("descrip") or "")
        remarks = str(payload.get("filing") or "")
        if not remarks:
            total = payload.get("total") or payload.get("current_num")
            if total:
                remarks = f"全{total}集"

        area = ""
        tags = payload.get("desc_tags") or payload.get("tags") or []
        if isinstance(tags, list) and tags:
            area = str(tags[0] if not isinstance(tags[0], dict) else tags[0].get("name") or "")

        eps = []
        theaters = payload.get("theaters") or []
        if isinstance(theaters, list):
            for item in theaters:
                if not isinstance(item, dict):
                    continue
                url = item.get("son_video_url") or item.get("son_video_h265_url") or item.get("video_url")
                if not url:
                    continue
                num = item.get("num") or (len(eps) + 1)
                eps.append(f"{num}${url}")

        if not eps and payload.get("video_url"):
            eps = [f"1${payload.get('video_url')}"]

        if not eps:
            return {"list": []}

        return {
            "list": [
                {
                    "vod_id": did,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_content": intro,
                    "vod_remarks": remarks,
                    "vod_area": area,
                    "vod_play_from": "星芽",
                    "vod_play_url": "#".join(eps),
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": {
                "User-Agent": self.UA,
                "Referer": "https://app.whjzjx.cn/",
            },
        }

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, page):
        data = self._post("/v3/search", body={"text": str(key or "")})
        rows = (((data.get("data") or {}).get("theater") or {}).get("search_data")) or []
        videos = []
        for vod in rows:
            if not isinstance(vod, dict):
                continue
            videos.append(
                {
                    "vod_id": str(vod.get("id") or ""),
                    "vod_name": str(vod.get("title") or ""),
                    "vod_pic": str(vod.get("cover_url") or ""),
                    "vod_remarks": str(vod.get("score_str") or ""),
                }
            )
        return {
            "list": videos,
            "page": int(page or 1),
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    def localProxy(self, params):
        return None

    @staticmethod
    def _parse_list(data):
        videos = []
        rows = ((data.get("data") or {}).get("list")) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            th = row.get("theater") if isinstance(row.get("theater"), dict) else row
            if not isinstance(th, dict):
                continue
            vid = th.get("id")
            name = th.get("title")
            if not vid or not name:
                continue
            remark = th.get("theme") or th.get("play_amount_str") or ""
            if not remark and th.get("total"):
                remark = f"全{th.get('total')}集"
            videos.append(
                {
                    "vod_id": str(vid),
                    "vod_name": str(name),
                    "vod_pic": str(th.get("cover_url") or ""),
                    "vod_remarks": str(remark or ""),
                }
            )
        return videos
