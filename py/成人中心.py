# coding=utf-8
# OK影视 / FongMi type=3
# 成人中心：搜索框输入密码解锁后，列出成人源并可浏览采集站
# 配置示例见文件末尾注释
import json
import sys
import time
from urllib.parse import quote, unquote

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def init(self, extend="{}"):
        self.host = ""
        self.UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.headers = {"User-Agent": self.UA, "Accept": "application/json,text/plain,*/*"}
        self.password = "888888"
        self.sources_url = ""
        self.static_sources = []
        # extend: {"password":"888888","sources_url":"https://.../iptv.txt?pwd=888888"}
        # 或 {"password":"888888","sources":[{"name":"xx","api":"https://.../provide/vod/"}]}
        try:
            if extend and str(extend).strip() not in ("", "{}", "null"):
                cfg = json.loads(extend) if isinstance(extend, str) else (extend or {})
            else:
                cfg = {}
        except Exception:
            cfg = {}
        if isinstance(cfg, dict):
            if cfg.get("password"):
                self.password = str(cfg.get("password")).strip()
            if cfg.get("pwd"):
                self.password = str(cfg.get("pwd")).strip()
            if cfg.get("sources_url"):
                self.sources_url = str(cfg.get("sources_url")).strip()
            if isinstance(cfg.get("sources"), list):
                self.static_sources = cfg.get("sources")
        # 默认：从密码门订阅拉成人源（可改）
        if not self.sources_url and not self.static_sources:
            self.sources_url = "https://dingyue.sjzkn.workers.dev/iptv.txt?pwd=" + quote(
                self.password, safe=""
            )
        self.session = None
        try:
            import requests
            from requests.adapters import HTTPAdapter

            self.session = requests.Session()
            self.session.verify = False
            self.session.headers.update(self.headers)
            ad = HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=1)
            self.session.mount("https://", ad)
            self.session.mount("http://", ad)
        except Exception:
            self.session = None

    def getName(self):
        return "成人中心"

    def isVideoFormat(self, url):
        return bool(url and (".m3u8" in str(url) or ".mp4" in str(url)))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            if self.session:
                self.session.close()
        except Exception:
            pass

    def _get(self, url, timeout=15):
        try:
            if self.session:
                r = self.session.get(url, timeout=timeout)
                return r.status_code, r.text, r.content
            import requests

            r = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
            return r.status_code, r.text, r.content
        except Exception:
            return 0, "", b""

    def _get_json(self, url, timeout=15):
        code, text, _ = self._get(url, timeout=timeout)
        if code != 200 or not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _token(self):
        # 简单令牌，带在 vod_id 里跨请求校验（壳会多次 new Spider）
        return "U" + self.password

    def _check_token(self, s):
        return str(s or "").startswith("U") and str(s)[1:] == self.password

    def _load_sources(self):
        out = []
        if self.static_sources:
            for i, s in enumerate(self.static_sources):
                if not isinstance(s, dict):
                    continue
                api = str(s.get("api") or s.get("url") or "").strip()
                name = str(s.get("name") or s.get("key") or f"源{i+1}").strip()
                if not api:
                    continue
                out.append({"name": name, "api": api, "type": s.get("type", 1)})
        if self.sources_url:
            data = self._get_json(self.sources_url)
            sites = data.get("sites") if isinstance(data, dict) else []
            if isinstance(sites, list):
                for s in sites:
                    if not isinstance(s, dict):
                        continue
                    name = str(s.get("name") or "")
                    group = str(s.get("group") or "")
                    api = str(s.get("api") or "").strip()
                    if not api:
                        continue
                    # 只要成人相关
                    if group == "成人" or "🔞" in name or "成人" in name:
                        out.append(
                            {
                                "name": name,
                                "api": api,
                                "type": s.get("type", 3),
                                "key": s.get("key"),
                            }
                        )
        # 去重
        seen = set()
        uniq = []
        for s in out:
            k = s["api"]
            if k in seen:
                continue
            seen.add(k)
            uniq.append(s)
        return uniq

    def _is_cms(self, api):
        a = str(api or "").lower()
        return "provide/vod" in a or "api.php" in a or "/vod/" in a

    def _cms_list(self, api, pg=1):
        api = str(api).strip()
        if not api:
            return [], 0
        if "ac=" not in api:
            api += ("&" if "?" in api else "?") + "ac=detail"
        # 列表优先
        list_api = api
        if "ac=detail" in list_api:
            list_api = list_api.replace("ac=detail", "ac=list")
        elif "ac=list" not in list_api:
            list_api += ("&" if "?" in list_api else "?") + "ac=list"
        list_api += f"&pg={int(pg)}"
        data = self._get_json(list_api)
        lst = data.get("list") or data.get("data") or []
        if isinstance(lst, dict):
            lst = lst.get("list") or []
        total = int(data.get("total") or data.get("pagecount") or len(lst) or 0)
        videos = []
        for it in lst if isinstance(lst, list) else []:
            if not isinstance(it, dict):
                continue
            vid = str(it.get("vod_id") or it.get("id") or "")
            if not vid:
                continue
            videos.append(
                {
                    "vod_id": f"{self._token()}|cms|{quote(api, safe='')}|{vid}",
                    "vod_name": str(it.get("vod_name") or it.get("name") or vid),
                    "vod_pic": str(it.get("vod_pic") or it.get("pic") or ""),
                    "vod_remarks": str(it.get("vod_remarks") or it.get("remarks") or ""),
                }
            )
        return videos, total

    def homeContent(self, filter):
        return {
            "class": [
                {"type_name": "🔒请搜索密码解锁", "type_id": "lock"},
                {"type_name": "使用说明", "type_id": "help"},
            ],
            "filters": {},
            "list": [],
        }

    def homeVideoContent(self):
        return {
            "list": [
                {
                    "vod_id": "tip",
                    "vod_name": "🔒 请在顶部搜索框输入密码解锁",
                    "vod_pic": "",
                    "vod_remarks": "解锁后显示成人源",
                }
            ]
        }

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "")
        pg = int(pg or 1)
        if tid == "help" or tid == "lock":
            return {
                "list": [
                    {
                        "vod_id": "tip2",
                        "vod_name": "在搜索框输入密码后回车",
                        "vod_remarks": "默认密码见站长",
                    },
                    {
                        "vod_id": "tip3",
                        "vod_name": "解锁后点源名称进入",
                        "vod_remarks": "采集站可直接看",
                    },
                ],
                "page": 1,
                "pagecount": 1,
                "limit": 20,
                "total": 2,
            }
        # tid = token|src|index 或 token|cms|api|page
        parts = tid.split("|")
        if len(parts) >= 2 and self._check_token(parts[0]):
            if parts[1] == "src" and len(parts) >= 3:
                # 列出某源下内容
                try:
                    idx = int(parts[2])
                except Exception:
                    idx = 0
                sources = self._load_sources()
                if idx < 0 or idx >= len(sources):
                    return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
                src = sources[idx]
                api = src.get("api") or ""
                if self._is_cms(api):
                    videos, total = self._cms_list(api, pg)
                    limit = 20
                    pagecount = max(1, (total + limit - 1) // limit) if total else max(pg, 1)
                    return {
                        "list": videos,
                        "page": pg,
                        "pagecount": pagecount,
                        "limit": limit,
                        "total": total or len(videos),
                    }
                # py 源无法在本爬虫内直接跑，给出提示条目
                return {
                    "list": [
                        {
                            "vod_id": f"{self._token()}|info|{idx}",
                            "vod_name": src.get("name") or "PY源",
                            "vod_remarks": "PY源请单独添加订阅",
                            "vod_pic": "",
                        }
                    ],
                    "page": 1,
                    "pagecount": 1,
                    "limit": 1,
                    "total": 1,
                }
        return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, array):
        raw = str(array[0] if isinstance(array, list) else array)
        if raw in ("tip", "tip2", "tip3", "wrong"):
            return {
                "list": [
                    {
                        "vod_id": raw,
                        "vod_name": "请使用搜索框输入密码",
                        "vod_content": "在成人中心顶部搜索框输入密码并搜索，解锁后选择源。",
                        "vod_play_from": "说明",
                        "vod_play_url": "说明$http://127.0.0.1/null",
                    }
                ]
            }
        parts = raw.split("|")
        if not parts or not self._check_token(parts[0]):
            return {
                "list": [
                    {
                        "vod_id": "deny",
                        "vod_name": "未解锁或令牌无效",
                        "vod_content": "请重新搜索密码解锁",
                        "vod_play_from": "说明",
                        "vod_play_url": "说明$http://127.0.0.1/null",
                    }
                ]
            }
        if parts[1] == "info":
            return {
                "list": [
                    {
                        "vod_id": raw,
                        "vod_name": "该条目为 PY 爬虫源",
                        "vod_content": "无法在中心内嵌运行其它 PY。请将源单独加入订阅，或改用采集站 API。",
                        "vod_play_from": "说明",
                        "vod_play_url": "说明$http://127.0.0.1/null",
                    }
                ]
            }
        if parts[1] == "site":
            # 源入口
            idx = int(parts[2]) if len(parts) > 2 else 0
            sources = self._load_sources()
            src = sources[idx] if 0 <= idx < len(sources) else {}
            name = src.get("name") or "源"
            api = src.get("api") or ""
            # 用假播放地址把用户带去分类：很多壳会直接播；改为只展示详情+推荐分类 id
            return {
                "list": [
                    {
                        "vod_id": f"{self._token()}|src|{idx}",
                        "vod_name": name,
                        "vod_content": f"API: {api}\n\n若为采集站：请返回分类进入「已解锁源」列表点进本源。\n若为PY源：请单独添加到订阅。",
                        "vod_play_from": "打开",
                        "vod_play_url": f"列表${self._token()}|src|{idx}",
                    }
                ]
            }
        if parts[1] == "cms" and len(parts) >= 4:
            api = unquote(parts[2])
            vod_id = parts[3]
            # 详情
            detail_api = api
            if "ac=" not in detail_api:
                detail_api += ("&" if "?" in detail_api else "?") + "ac=detail"
            else:
                detail_api = detail_api.replace("ac=list", "ac=detail")
            detail_api += f"&ids={vod_id}"
            data = self._get_json(detail_api)
            lst = data.get("list") or []
            it = lst[0] if isinstance(lst, list) and lst else {}
            if not it:
                return {"list": []}
            play_from = str(it.get("vod_play_from") or "播放")
            play_url = str(it.get("vod_play_url") or "")
            return {
                "list": [
                    {
                        "vod_id": raw,
                        "vod_name": str(it.get("vod_name") or ""),
                        "vod_pic": str(it.get("vod_pic") or ""),
                        "vod_content": str(it.get("vod_content") or ""),
                        "vod_play_from": play_from,
                        "vod_play_url": play_url,
                    }
                ]
            }
        return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        key = str(key or "").strip()
        if not key:
            return {"list": []}
        if key != self.password:
            return {
                "list": [
                    {
                        "vod_id": "wrong",
                        "vod_name": "❌ 密码错误",
                        "vod_remarks": "请重试",
                        "vod_pic": "",
                    }
                ]
            }
        # 密码正确：列出成人源
        sources = self._load_sources()
        videos = []
        for i, s in enumerate(sources):
            api = s.get("api") or ""
            kind = "采集" if self._is_cms(api) else "PY"
            videos.append(
                {
                    "vod_id": f"{self._token()}|site|{i}",
                    "vod_name": s.get("name") or f"源{i+1}",
                    "vod_remarks": kind,
                    "vod_pic": "",
                }
            )
        if not videos:
            videos = [
                {
                    "vod_id": "tip",
                    "vod_name": "已解锁，但未拉到成人源",
                    "vod_remarks": "检查 sources_url",
                }
            ]
        # 同时把可浏览的采集站做成分类入口（type_id 风格通过 category 再进）
        # 搜索结果点进去是 detail；采集站再在 detail 说明
        # 为方便：把 cms 源额外用可分类 id 提示
        return {
            "list": videos,
            "page": 1,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        # cms 播放地址直接在 detail 的 vod_play_url；此处兜底
        url = str(id or "")
        if url.startswith("http"):
            return {
                "url": url,
                "parse": 0,
                "jx": 0,
                "header": self.headers,
            }
        return {
            "url": "",
            "parse": 0,
            "jx": 0,
            "header": self.headers,
        }

    def localProxy(self, param):
        return None


# ========== 订阅配置示例 ==========
# {
#   "key": "adult_center",
#   "name": "🔒成人中心",
#   "type": 3,
#   "api": "https://188.sjzkn1.tk/py/成人中心.py",
#   "searchable": 1,
#   "quickSearch": 0,
#   "filterable": 0,
#   "changeable": 0,
#   "ext": "{\"password\":\"888888\",\"sources_url\":\"https://188.sjzkn1.tk/00.json\"}"
# }
#
# 使用：进入源 → 搜索框输入 888888 → 显示成人源列表
# 采集站可继续点开浏览；PY 源需单独添加订阅
