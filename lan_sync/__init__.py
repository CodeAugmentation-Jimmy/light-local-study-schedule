"""学习记录的设备计数合并，以及仅在用户启用时运行的局域网接口。"""
from copy import deepcopy
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import math
from pathlib import Path
import re
import secrets
import socket
import threading
import uuid
from .schedule import validate_schedule


PROTOCOL = 2
MAX_BODY = 8 * 1024 * 1024


def validate_document(document):
    if not isinstance(document, dict) or document.get("protocol") != PROTOCOL or not isinstance(document.get("items"), list):
        raise ValueError("课程表同步需要电脑和手机均升级至 1.2 或更高版本")
    if len(document["items"]) > 10000:
        raise ValueError("类目数量过多")
    seen = set()
    for item in document["items"]:
        if not isinstance(item, dict):
            raise ValueError("类目格式有误")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identifier) or identifier in seen:
            raise ValueError("类目编号有误或重复")
        seen.add(identifier)
        if not isinstance(item.get("name"), str) or not item["name"].strip() or len(item["name"]) > 200:
            raise ValueError("类目名称须为 1 至 200 个字符")
        if type(item.get("goal")) is not int or not 1 <= item["goal"] <= 1000000:
            raise ValueError("每日目标须为 1 至 1000000 分钟")
        validate_schedule(item.get("schedule"))
        rev = item.get("rev")
        if not isinstance(rev, list) or len(rev) != 2 or type(rev[0]) is not int or not 0 <= rev[0] < 2**53 or not isinstance(rev[1], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", rev[1]):
            raise ValueError("版本格式有误")
        if type(item.get("deleted")) is not bool or not isinstance(item.get("counters"), dict):
            raise ValueError("记录格式有误")
        for day, counters in item["counters"].items():
            if date.fromisoformat(day).isoformat() != day or not isinstance(counters, dict):
                raise ValueError("日期格式有误")
            for device, value in counters.items():
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", device) or type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1e12:
                    raise ValueError("学习时长有误")
    return document


def merge_documents(left, right):
    """按设备取最大累计值，删除标记优先，元数据使用逻辑版本。"""
    validate_document(left)
    validate_document(right)
    merged = {item["id"]: deepcopy(item) for item in left["items"]}
    for remote in right["items"]:
        local = merged.get(remote["id"])
        if local is None:
            merged[remote["id"]] = deepcopy(remote)
            continue
        winner = deepcopy(max((local, remote), key=lambda item: tuple(item["rev"])))
        winner["deleted"] = local["deleted"] or remote["deleted"]
        for source in (local, remote):
            for day, counters in source["counters"].items():
                target = winner["counters"].setdefault(day, {})
                for device, value in counters.items():
                    target[device] = max(target.get(device, 0), value)
        merged[remote["id"]] = winner
    return {"protocol": PROTOCOL, "items": sorted(merged.values(), key=lambda item: item["id"])}


def records(item):
    return {day: sum(counters.values()) for day, counters in item["counters"].items()}


class Ledger:
    def __init__(self, device, stored=()):
        self.device = device
        entries = []
        for old in stored:
            meta = old.get("_sync")
            if meta is not None:
                entries.append({"id": old["id"], "name": old["name"], "goal": old["goal"], **deepcopy(meta)})
            else:
                entries.append({"id": old["id"], "name": old["name"], "goal": old["goal"], "rev": [1, "legacy"], "deleted": False,
                                "counters": {day: {"legacy": value} for day, value in old["records"].items()}})
            entries[-1]["schedule"] = deepcopy(old.get("schedule", {"mode": "daily"}))
        self.document = validate_document({"protocol": PROTOCOL, "items": entries})

    def next_revision(self):
        return [max((item["rev"][0] for item in self.document["items"]), default=0) + 1, self.device]

    def capture(self, active):
        by_id = {item["id"]: item for item in self.document["items"]}
        active_ids = {item["id"] for item in active}
        for item in self.document["items"]:
            if not item["deleted"] and item["id"] not in active_ids:
                item["deleted"] = True
                item["rev"] = self.next_revision()
        for source in active:
            rule = deepcopy(source.get("schedule", {"mode": "daily"}))
            validate_schedule(rule)
            target = by_id.get(source["id"])
            if target is None:
                target = {"id": source["id"], "name": source["name"], "goal": source["goal"], "schedule": rule, "rev": self.next_revision(), "deleted": False, "counters": {}}
                self.document["items"].append(target)
                by_id[source["id"]] = target
            if target["deleted"]:
                continue
            if (target["name"], target["goal"], target["schedule"]) != (source["name"], source["goal"], rule):
                target.update(name=source["name"], goal=source["goal"], schedule=rule, rev=self.next_revision())
            previous = records(target)
            for day, seconds in source["records"].items():
                delta = max(0, seconds - previous.get(day, 0))
                if delta:
                    counters = target["counters"].setdefault(day, {})
                    counters[self.device] = counters.get(self.device, 0) + delta
        validate_document(self.document)

    def active(self):
        return [{"id": item["id"], "name": item["name"], "goal": item["goal"], "schedule": deepcopy(item["schedule"]), "records": records(item)} for item in self.document["items"] if not item["deleted"]]

    def stored(self):
        return [{"id": item["id"], "name": item["name"], "goal": item["goal"], "schedule": deepcopy(item["schedule"]), "records": records(item), "_sync": {key: deepcopy(item[key]) for key in ("rev", "deleted", "counters")}} for item in self.document["items"]]

    def merge(self, document):
        self.document = merge_documents(self.document, document)


def load_settings(path):
    path = Path(path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("device"), str) or not isinstance(data.get("token"), str) or not re.fullmatch(r"[a-f0-9]{32}", data["device"]) or not re.fullmatch(r"[A-F0-9]{12}", data["token"]):
            raise ValueError("同步设置损坏，请保留原文件后检查")
        return data
    data = {"device": uuid.uuid4().hex, "token": secrets.token_hex(6).upper()}
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def local_addresses(port):
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if ipaddress.ip_address(address).is_private and not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return [f"http://{address}:{port}" for address in sorted(addresses)]


class SyncServer:
    def __init__(self, token, exchange, host="0.0.0.0", port=8765):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def reply(self, status, data):
                body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                try:
                    if not ipaddress.ip_address(self.client_address[0]).is_private:
                        self.reply(403, {"error": "仅允许局域网连接"})
                        return
                    if self.path != "/sync":
                        self.reply(404, {"error": "接口不存在"})
                        return
                    if self.headers.get("Origin") or not hmac.compare_digest(self.headers.get("X-Study-Token", ""), token):
                        self.reply(401, {"error": "配对码不正确"})
                        return
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= MAX_BODY:
                        self.reply(413, {"error": "同步数据大小有误"})
                        return
                    document = json.loads(self.rfile.read(length))
                    validate_document(document)
                    self.reply(200, exchange(document))
                except (ValueError, TypeError, KeyError) as error:
                    self.reply(400, {"error": str(error)})
                except (TimeoutError, OSError):
                    self.reply(503, {"error": "电脑忙或无法保存，请稍后重试"})

        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
