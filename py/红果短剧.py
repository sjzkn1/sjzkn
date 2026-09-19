# -*- coding: utf-8 -*-
"""
红果短剧 - OK影视 Python 点播源
站点: https://www.hongguoapp.cn
列表: /vodshow/51-----------.html
排序: 最新 time / 最热 hits
"""

import json
import re
import sys
from urllib.parse import quote

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    host = "https://www.hongguoapp.cn"
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    # 排序 + 题材
    GENRES = [
        "全部",
        "最新",
        "最热",
        "古装",
        "战争",
        "青春偶像",
        "喜剧",
        "家庭",
        "犯罪",
        "动作",
        "奇幻",
        "剧情",
        "历史",
        "经典",
        "乡村",
        "情景",
        "商战",
        "网剧",
        "其他",
    ]

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._pagecount = 1
        try:
            import requests
            from requests.adapters import HTTPAdapter

            self.session = requests.Session()
            self.session.headers.update(self.headers)
            self.session.verify = False
            ad = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=1)
            self.session.mount("https://", ad)
            self.session.mount("http://", ad)
        except Exception:
            self.session = None

    def getName(self):
        return "红果短剧"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _get(self, url, timeout=18):
        try:
            if self.session:
                r = self.session.get(url, timeout=timeout)
                return r.status_code, r.text
            import urllib.request
            import ssl

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.status, resp.read().decode("utf-8", "ignore")
        except Exception:
            return 0, ""

    def homeContent(self, filter):
        classes = []
        for name in self.GENRES:
            tid = "all" if name == "全部" else name
            classes.append({"type_id": tid, "type_name": name})
        return {"class": classes, "filters": {}, "filterable": 0}

    def homeVideoContent(self):
        return {"list": self._list_page("最新", 1)[:16]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or "all")
        videos = self._list_page(tid, pg)
        pagecount = max(int(self._pagecount or 1), 1)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": 36,
            "total": pagecount * 36,
        }

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        st, html = self._get(f"{self.host}/voddetail/{vid}.html")
        if st != 200 or not html:
            return {"list": []}

        title = self._m(html, r"<h(?:1|2)[^>]*>([^<]+)") or f"短剧{vid}"
        pic = self._m(html, r'data-original="([^"]+)"') or self._m(
            html, r'(?:src|data-src)="([^"]*upload/vod[^"]+)"'
        )
        if pic and pic.startswith("/"):
            pic = self.host + pic
        content = self._m(
            html, r'class="[^"]*hl-content-text[^"]*"[^>]*>([\s\S]*?)</(?:div|span|p)>'
        )
        content = self._strip(content) if content else title
        remarks = self._m(html, r"备注[：:]\s*</?[a-z]+[^>]*>\s*([^<]+)") or self._m(
            html, r'class="[^"]*remarks[^"]*"[^>]*>([^<]+)'
        )
        remarks = self._strip(remarks or "")

        eps = []
        seen = set()
        for m in re.finditer(
            rf'href="(/vodplay/{re.escape(vid)}-(\d+)-(\d+)\.html)"[^>]*>([^<]*)',
            html,
        ):
            sid, ep, name = m.group(2), m.group(3), self._strip(m.group(4))
            key = f"{sid}-{ep}"
            if key in seen:
                continue
            seen.add(key)
            if not name:
                name = f"第{ep}集"
            eps.append(f"{name}${vid}-{sid}-{ep}")
        if not eps:
            eps = [f"第1集${vid}-1-1"]

        return {
            "list": [
                {
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic or "",
                    "vod_remarks": remarks,
                    "vod_content": content,
                    "vod_play_from": "红果短剧",
                    "vod_play_url": "#".join(eps),
                }
            ]
        }

    def playerContent(self, flag, id, vipFlags):
        key = str(id or "").strip()
        play_url = ""
        if re.match(r"^\d+-\d+-\d+$", key):
            st, html = self._get(f"{self.host}/vodplay/{key}.html")
            if st == 200 and html:
                play_url = self._extract_play_url(html)
        elif key.isdigit():
            st, html = self._get(f"{self.host}/vodplay/{key}-1-1.html")
            if st == 200 and html:
                play_url = self._extract_play_url(html)
        elif key.startswith("http"):
            play_url = key
        return {
            "parse": 0 if play_url else 1,
            "url": play_url or "",
            "header": {
                "User-Agent": self.UA,
                "Referer": self.host + "/",
                "Origin": self.host,
            },
        }

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg or 1)
        kw = quote(str(key or ""))
        urls = [
            f"{self.host}/vodsearch/{kw}-------------.html",
            f"{self.host}/vodsearch/-------------.html?wd={kw}&page={pg}",
            f"{self.host}/index.php/vod/search/page/{pg}/wd/{kw}.html",
        ]
        videos = []
        for url in urls:
            st, html = self._get(url)
            if st != 200 or not html:
                continue
            videos = self._parse_list(html)
            if videos:
                break
        return {"list": videos, "page": int(pg)}

    # ---------- list ----------
    def _list_url(self, tid, pg):
        pg = int(pg or 1)
        tid = str(tid or "all")
        # 最新: /vodshow/51--time---------.html
        # 分页: /vodshow/51--time------2---.html
        if tid in ("最新", "time", "new"):
            if pg <= 1:
                return f"{self.host}/vodshow/51--time---------.html"
            return f"{self.host}/vodshow/51--time------{pg}---.html"
        # 最热: /vodshow/51--hits---------.html
        if tid in ("最热", "hits", "hot"):
            if pg <= 1:
                return f"{self.host}/vodshow/51--hits---------.html"
            return f"{self.host}/vodshow/51--hits------{pg}---.html"
        if tid in ("all", "51", ""):
            if pg <= 1:
                return f"{self.host}/vodshow/51-----------.html"
            return f"{self.host}/vodshow/51--------{pg}---.html"
        # 题材
        cls = quote(tid)
        if pg <= 1:
            return f"{self.host}/vodshow/51---{cls}--------.html"
        return f"{self.host}/vodshow/51---{cls}-----{pg}---.html"

    def _list_page(self, tid, pg):
        url = self._list_url(tid, pg)
        st, html = self._get(url)
        if st != 200 or not html:
            self._pagecount = 1
            return []
        tid_s = str(tid or "")
        pages = []
        if tid_s in ("最新", "time", "new"):
            pages = [
                int(x)
                for x in re.findall(r"/vodshow/51--time------(\d+)---\.html", html)
            ]
        elif tid_s in ("最热", "hits", "hot"):
            pages = [
                int(x)
                for x in re.findall(r"/vodshow/51--hits------(\d+)---\.html", html)
            ]
        elif tid_s in ("all", "51", ""):
            pages = [
                int(x) for x in re.findall(r"/vodshow/51--------(\d+)---\.html", html)
            ]
        else:
            cls = quote(tid_s)
            pages = [
                int(x)
                for x in re.findall(
                    rf"/vodshow/51---{re.escape(cls)}-----(\d+)---\.html", html
                )
            ]
            if not pages:
                pages = [
                    int(x)
                    for x in re.findall(
                        r"/vodshow/51---[^\"']*?-----(\d+)---\.html", html
                    )
                ]
        self._pagecount = max(pages) if pages else max(int(pg or 1), 1)
        return self._parse_list(html)

    def _parse_list(self, html):
        out = []
        seen = set()
        html = html or ""
        patterns = [
            r'href="/voddetail/(\d+)\.html"\s+title="([^"]+)"\s+data-original="([^"]+)"',
            r'href="/voddetail/(\d+)\.html"[^>]*title="([^"]+)"[^>]*data-original="([^"]+)"',
            r'data-original="([^"]+)"[^>]*href="/voddetail/(\d+)\.html"[^>]*title="([^"]+)"',
        ]
        for idx, pat in enumerate(patterns):
            for m in re.finditer(pat, html):
                if idx == 2:
                    pic, vid, name = m.group(1), m.group(2), m.group(3)
                else:
                    vid, name, pic = m.group(1), m.group(2), m.group(3)
                if vid in seen:
                    continue
                seen.add(vid)
                if pic.startswith("/"):
                    pic = self.host + pic
                tail = html[m.end() : m.end() + 220]
                rem = re.search(r'class="[^"]*remarks[^"]*"[^>]*>([^<]+)', tail)
                remarks = self._strip(rem.group(1)) if rem else ""
                out.append(
                    {
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": pic,
                        "vod_remarks": remarks,
                    }
                )
            if out:
                break
        return out

    def _extract_play_url(self, html):
        m = re.search(r"player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?\s*</script>", html or "")
        if not m:
            m = re.search(
                r"var\s+player_[a-zA-Z0-9]+\s*=\s*(\{[\s\S]*?\})\s*;", html or ""
            )
        if m:
            try:
                j = json.loads(m.group(1))
                url = str(j.get("url") or "")
                enc = j.get("encrypt")
                if enc in (1, "1"):
                    from urllib.parse import unquote

                    url = unquote(url)
                elif enc in (2, "2"):
                    import base64
                    from urllib.parse import unquote

                    url = unquote(base64.b64decode(url).decode("utf-8", "ignore"))
                if url.startswith("http"):
                    return url
            except Exception:
                pass
        m = re.search(r'(https?://[^"\'\\]+\.m3u8[^"\'\\]*)', html or "")
        return m.group(1) if m else ""

    @staticmethod
    def _m(s, pat):
        m = re.search(pat, s or "", re.I)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _strip(t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        for a, b in (
            ("&nbsp;", " "),
            ("&amp;", "&"),
            ("&lt;", "<"),
            ("&gt;", ">"),
            ("&quot;", '"'),
            ("&#39;", "'"),
        ):
            t = t.replace(a, b)
        return re.sub(r"\s+", " ", t).strip()
