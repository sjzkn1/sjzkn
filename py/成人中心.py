# coding=utf-8
# OK影视 / FongMi type=3
# 成人中心：搜索密码解锁 → 列出成人源（含 PY）→ 直接调用远程 PY 爬虫
import json
import sys
import time
import hashlib
import types
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
        self.UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.headers = {"User-Agent": self.UA, "Accept": "application/json,text/plain,*/*"}
        self.password = "888888"
        self.sources_url = ""
        self.static_sources = []
        self._spider_cache = {}
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
        if not self.sources_url and not self.static_sources:
            self.sources_url = "https://188.sjzkn1.tk/00.json"
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

    def _get(self, url, timeout=20):
        try:
            if self.session:
                r = self.session.get(url, timeout=timeout)
                return r.status_code, r.text, r.content
            import requests
            r = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
            return r.status_code, r.text, r.content
        except Exception:
            return 0, "", b""

    def _get_json(self, url, timeout=20):
        code, text, _ = self._get(url, timeout=timeout)
        if code != 200 or not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            return {}

    def _token(self):
        return "U" + self.password

    def _check_token(self, s):
        return str(s or "").startswith("U") and str(s)[1:] == self.password

    def _is_adult_site(self, s):
        if not isinstance(s, dict):
            return False
        g = str(s.get("group") or "")
        n = str(s.get("name") or "")
        if g == "成人":
            return True
        if "🔞" in n or "成人" in n:
            return True
        return False

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
                out.append({"name": name, "api": api, "type": int(s.get("type") or 3)})
        if self.sources_url:
            data = self._get_json(self.sources_url)
            sites = data.get("sites") if isinstance(data, dict) else []
            if isinstance(sites, list):
                for s in sites:
                    if not self._is_adult_site(s):
                        continue
                    api = str(s.get("api") or "").strip()
                    if not api:
                        continue
                    out.append(
                        {
                            "name": str(s.get("name") or api),
                            "api": api,
                            "type": int(s.get("type") or 3),
                            "key": s.get("key"),
                            "ext": s.get("ext") or "",
                        }
                    )
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
        return "provide/vod" in a or ("api.php" in a and not a.endswith(".py"))

    def _is_py(self, api):
        a = str(api or "").lower()
        return a.endswith(".py") or "/py/" in a

    def _cms_list(self, api, pg=1):
        api = str(api).strip()
        if not api:
            return [], 0
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

    def _get_remote_spider(self, api_url, ext=""):
        """下载并实例化远程 PY 爬虫"""
        key = api_url + "||" + str(ext or "")
        if key in self._spider_cache:
            return self._spider_cache[key]
        code_status, code, _ = self._get(api_url, timeout=25)
        if code_status != 200 or not code or "class Spider" not in code:
            return None
        try:
            mod = types.ModuleType("remote_spider_" + hashlib.md5(api_url.encode()).hexdigest()[:10])
            # 注入常见依赖路径
            mod.__dict__["__name__"] = mod.__name__
            exec(compile(code, api_url, "exec"), mod.__dict__)
            cls = getattr(mod, "Spider", None)
            if cls is None:
                return None
            inst = cls()
            try:
                if hasattr(inst, "init"):
                    inst.init(ext if ext is not None else "")
                elif hasattr(inst, "homeContent") is False:
                    pass
            except Exception:
                try:
                    inst.init("")
                except Exception:
                    pass
            self._spider_cache[key] = inst
            return inst
        except Exception:
            return None

    def _prefix_list(self, lst, src_idx):
        """给子爬虫返回的 list 中 vod_id 加前缀，方便回传"""
        out = []
        tok = self._token()
        for it in lst or []:
            if not isinstance(it, dict):
                continue
            vid = str(it.get("vod_id") or "")
            it2 = dict(it)
            it2["vod_id"] = f"{tok}|py|{src_idx}|{quote(vid, safe='')}"
            out.append(it2)
        return out

    def _call_py(self, src_idx, method, *args, **kwargs):
        sources = self._load_sources()
        if src_idx < 0 or src_idx >= len(sources):
            return None
        src = sources[src_idx]
        api = src.get("api") or ""
        if not self._is_py(api):
            return None
        sp = self._get_remote_spider(api, src.get("ext") or "")
        if sp is None:
            return None
        fn = getattr(sp, method, None)
        if not callable(fn):
            return None
        try:
            return fn(*args, **kwargs)
        except TypeError:
            try:
                return fn(*args)
            except Exception:
                return None
        except Exception:
            return None

    def homeContent(self, filter):
        return {
            "class": [
                {"type_name": "🔒搜索密码解锁", "type_id": "lock"},
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
                    "vod_name": "🔒 请在搜索框输入密码解锁成人源",
                    "vod_pic": "",
                    "vod_remarks": "支持PY源直接进入",
                }
            ]
        }

    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or "")
        pg = int(pg or 1)
        if tid in ("help", "lock"):
            return {
                "list": [
                    {
                        "vod_id": "tip2",
                        "vod_name": "在搜索框输入密码后回车",
                        "vod_remarks": "默认 888888",
                    },
                    {
                        "vod_id": "tip3",
                        "vod_name": "解锁后点源名称进入分类",
                        "vod_remarks": "PY源可直接浏览",
                    },
                ],
                "page": 1,
                "pagecount": 1,
                "limit": 20,
                "total": 2,
            }
        parts = tid.split("|")
        if len(parts) >= 2 and self._check_token(parts[0]):
            # token|src|idx  → 源首页分类列表转成视频 或 调 py homeVideo / category
            if parts[1] == "src" and len(parts) >= 3:
                try:
                    idx = int(parts[2])
                except Exception:
                    idx = -1
                sources = self._load_sources()
                if idx < 0 or idx >= len(sources):
                    return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
                src = sources[idx]
                api = src.get("api") or ""
                # CMS
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
                # PY：先取 homeContent 分类，把分类当列表；或 homeVideoContent
                if self._is_py(api):
                    # pg==1 时列出分类作为入口；若有 class 则展示 class
                    if pg <= 1:
                        home = self._call_py(idx, "homeContent", False)
                        classes = (home or {}).get("class") or (home or {}).get("class_list") or []
                        videos = []
                        if classes:
                            for c in classes:
                                if not isinstance(c, dict):
                                    continue
                                cid = str(c.get("type_id") or c.get("type_name") or "")
                                cname = str(c.get("type_name") or cid)
                                videos.append(
                                    {
                                        "vod_id": f"{self._token()}|pycat|{idx}|{quote(cid, safe='')}",
                                        "vod_name": cname,
                                        "vod_remarks": "分类",
                                        "vod_pic": "",
                                    }
                                )
                        hv = self._call_py(idx, "homeVideoContent")
                        if isinstance(hv, dict) and hv.get("list"):
                            videos.extend(self._prefix_list(hv.get("list"), idx))
                        if videos:
                            return {
                                "list": videos,
                                "page": 1,
                                "pagecount": 1,
                                "limit": len(videos),
                                "total": len(videos),
                            }
                    # 无分类则尝试 categoryContent 默认 tid
                    data = self._call_py(idx, "categoryContent", "0", str(pg), True, {})
                    if not data:
                        data = self._call_py(idx, "categoryContent", "", str(pg), True, {})
                    if isinstance(data, dict) and data.get("list") is not None:
                        lst = self._prefix_list(data.get("list"), idx)
                        return {
                            "list": lst,
                            "page": int(data.get("page") or pg),
                            "pagecount": int(data.get("pagecount") or 1),
                            "limit": int(data.get("limit") or 20),
                            "total": int(data.get("total") or len(lst)),
                        }
                    return {
                        "list": [
                            {
                                "vod_id": f"{self._token()}|info|{idx}",
                                "vod_name": src.get("name") or "PY源",
                                "vod_remarks": "加载失败",
                            }
                        ],
                        "page": 1,
                        "pagecount": 1,
                        "limit": 1,
                        "total": 1,
                    }
            # token|pycat|idx|type_id → 调远程 categoryContent
            if parts[1] == "pycat" and len(parts) >= 4:
                try:
                    idx = int(parts[2])
                except Exception:
                    idx = -1
                type_id = unquote(parts[3])
                data = self._call_py(idx, "categoryContent", type_id, str(pg), True, {})
                if isinstance(data, dict):
                    lst = self._prefix_list(data.get("list"), idx)
                    return {
                        "list": lst,
                        "page": int(data.get("page") or pg),
                        "pagecount": int(data.get("pagecount") or 1),
                        "limit": int(data.get("limit") or 20),
                        "total": int(data.get("total") or len(lst)),
                    }
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
        return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, array):
        raw = str(array[0] if isinstance(array, list) else array)
        if raw in ("tip", "tip2", "tip3", "wrong"):
            return {
                "list": [
                    {
                        "vod_id": raw,
                        "vod_name": "请使用搜索框输入密码",
                        "vod_content": "进入成人中心后，在搜索框输入密码并搜索。",
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
        # 源入口：点搜索结果里的源
        if parts[1] == "site" and len(parts) >= 3:
            try:
                idx = int(parts[2])
            except Exception:
                idx = -1
            sources = self._load_sources()
            src = sources[idx] if 0 <= idx < len(sources) else {}
            name = src.get("name") or "源"
            # 把「打开」指向分类 tid，部分壳不支持；提供说明 + 假列表提示用户进分类
            # 更稳妥：detail 里直接拉首页推荐
            api = src.get("api") or ""
            content = f"源：{name}\nAPI：{api}\n\n请返回后点击源进入分类浏览；或使用下方试看。"
            play_from = "进入"
            play_url = f"分类${self._token()}|src|{idx}"
            # 若是 PY，尝试取一条推荐作详情
            if self._is_py(api):
                hv = self._call_py(idx, "homeVideoContent")
                if isinstance(hv, dict) and hv.get("list"):
                    first = hv["list"][0]
                    fid = str(first.get("vod_id") or "")
                    if fid:
                        det = self._call_py(idx, "detailContent", [fid])
                        if isinstance(det, dict) and det.get("list"):
                            item = dict(det["list"][0])
                            # 改写 play id
                            pf = str(item.get("vod_play_from") or "播放")
                            pu = str(item.get("vod_play_url") or "")
                            # 包装播放串
                            item["vod_id"] = f"{self._token()}|py|{idx}|{quote(fid, safe='')}"
                            item["vod_name"] = name + " · " + str(item.get("vod_name") or "")
                            item["vod_content"] = content + "\n\n" + str(item.get("vod_content") or "")
                            # 播放地址加上 py 前缀标记在 playerContent 解析
                            item["vod_play_from"] = pf
                            item["vod_play_url"] = self._wrap_play(idx, pu)
                            return {"list": [item]}
            return {
                "list": [
                    {
                        "vod_id": f"{self._token()}|src|{idx}",
                        "vod_name": name,
                        "vod_content": content,
                        "vod_play_from": play_from,
                        "vod_play_url": play_url,
                    }
                ]
            }
        # PY 详情
        if parts[1] == "py" and len(parts) >= 4:
            try:
                idx = int(parts[2])
            except Exception:
                idx = -1
            vid = unquote(parts[3])
            det = self._call_py(idx, "detailContent", [vid])
            if isinstance(det, dict) and det.get("list"):
                item = dict(det["list"][0])
                item["vod_id"] = raw
                item["vod_play_url"] = self._wrap_play(idx, str(item.get("vod_play_url") or ""))
                return {"list": [item]}
            return {"list": []}
        # CMS 详情
        if parts[1] == "cms" and len(parts) >= 4:
            api = unquote(parts[2])
            vod_id = parts[3]
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
            return {
                "list": [
                    {
                        "vod_id": raw,
                        "vod_name": str(it.get("vod_name") or ""),
                        "vod_pic": str(it.get("vod_pic") or ""),
                        "vod_content": str(it.get("vod_content") or ""),
                        "vod_play_from": str(it.get("vod_play_from") or "播放"),
                        "vod_play_url": str(it.get("vod_play_url") or ""),
                    }
                ]
            }
        if parts[1] == "info":
            return {
                "list": [
                    {
                        "vod_id": raw,
                        "vod_name": "源加载失败",
                        "vod_content": "远程 PY 无法加载，请检查源地址。",
                        "vod_play_from": "说明",
                        "vod_play_url": "说明$http://127.0.0.1/null",
                    }
                ]
            }
        return {"list": []}

    def _wrap_play(self, idx, play_url):
        """把子源播放串加上索引标记，多线路用 $$$ / # 保持原样，只在每条 url 前加标记不破坏结构。
        playerContent 收到的是单条 id。
        """
        return str(play_url or "")

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
        sources = self._load_sources()
        videos = []
        for i, s in enumerate(sources):
            api = s.get("api") or ""
            if self._is_cms(api):
                kind = "采集"
            elif self._is_py(api):
                kind = "PY"
            else:
                kind = "源"
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
                    "vod_remarks": "检查 sources_url / 00.json",
                }
            ]
        return {
            "list": videos,
            "page": 1,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id or "")
        # 若是 py 详情来的直链
        if url.startswith("http"):
            return {"url": url, "parse": 0, "jx": 0, "header": self.headers}
        # 尝试：id 可能是  token|py|idx|realId 的播放，需要子爬虫 playerContent
        # 多数壳会把 vod_play_url 里 $ 后面的部分当 id 传入
        # 若子源返回的就是 http，上面已处理
        # 尝试解析包装
        parts = url.split("|")
        if len(parts) >= 4 and self._check_token(parts[0]) and parts[1] == "py":
            try:
                idx = int(parts[2])
            except Exception:
                idx = -1
            real = unquote("|".join(parts[3:]))
            data = self._call_py(idx, "playerContent", flag, real, vipFlags)
            if isinstance(data, dict) and data.get("url"):
                return data
            if real.startswith("http"):
                return {"url": real, "parse": 0, "jx": 0, "header": self.headers}
        return {"url": url if url.startswith("http") else "", "parse": 0, "jx": 0, "header": self.headers}

    def localProxy(self, param):
        return None
