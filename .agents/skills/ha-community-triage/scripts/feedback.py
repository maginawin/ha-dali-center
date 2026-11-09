#!/usr/bin/env python3
"""Collect HA GitHub feedback; remote writes require publish --apply."""

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo


def load(path):
    """Read a required JSON file."""
    return json.loads(Path(path).read_text())


def save(path, value):
    """Atomically replace JSON without exposing a partial checkpoint."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".next")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


@contextmanager
def locked(path):
    """Allow only one writer for this state file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def normalized(text):
    """Compare rich-text readback without Markdown presentation differences."""
    text = text.replace("\\\n", "\n")
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    return " ".join(html.unescape(re.sub("<[^>]+>", "", text)).split())


def spaced_text(text, existing=False):
    """Preserve paragraph gaps through Meegle rich-text conversion."""
    # Meegle preserves a leading Markdown hard break as an empty paragraph.
    # Read-back text uses four newlines for that gap and two for ordinary lines.
    minimum = 4 if existing else 2
    blocks = re.split(r"(\n{" + str(minimum) + r",})", text)
    for index in range(1, len(blocks), 2):
        following = blocks[index + 1]
        if not following or following.startswith("\\\n"):
            continue
        if re.match(r"(?:[-+*] |\d+[.)] |#+ |>|`{3}|~{3})", following):
            continue
        blocks[index] = "\n\n\\\n"
    return "".join(blocks)


def command(*args):
    """Run a CLI and require a successful JSON response."""
    result = subprocess.run(
        list(args), check=False, capture_output=True, text=True, timeout=60
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    data = json.loads(result.stdout)
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


def call(*args):
    """Call the logged-in Meegle CLI."""
    return command("meegle", *args)


def github_pages(endpoint):
    """Read every GitHub REST page using gh pagination."""
    pages = command(
        "gh",
        "api",
        "--hostname",
        "github.com",
        "--method",
        "GET",
        endpoint,
        "--paginate",
        "--slurp",
    )
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("GitHub 分页格式不符")
    return [item for page in pages for item in page]


def fingerprint(value):
    """Hash content deterministically, including edited comments."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def source_index(issues):
    """Index issue bodies and comments by their exact source URL."""
    return {
        post["url"]: post for issue in issues for post in [issue, *issue["comments"]]
    }


def values(item):
    """Index Meegle fields by their stable keys."""
    return {f["key"]: f.get("value") for f in item.get("work_item_fields", [])}


class Intake:
    """Coordinate read-only collection and explicit verified writes."""

    def __init__(self, config, state_path, cli=call, github=github_pages):
        """Bind configured sources, destination, state, and CLI clients."""
        self.c, self.path, self.cli, self.github = config, Path(state_path), cli, github
        self.config_fingerprint = fingerprint(config)

    def state(self):
        """Read state without creating a checkpoint on the first collection."""
        state = (
            load(self.path)
            if self.path.exists()
            else {
                "schema_version": 1,
                "config_fingerprint": self.config_fingerprint,
                "tracked_issues": [],
                "pending_writes": [],
            }
        )
        if (
            state["schema_version"] != 1
            or state["config_fingerprint"] != self.config_fingerprint
        ):
            raise ValueError("状态版本或配置不匹配，先核对已有映射")
        return state

    def validate_scan(self, scan):
        """Reject a different configuration or a superseded checkpoint."""
        state = self.state()
        if scan["config_fingerprint"] != self.config_fingerprint:
            raise ValueError("采集配置不匹配")
        if scan["base_checkpoint"] != state.get("last_successful_check_at"):
            raise ValueError("检查进度已变化，重新采集后再处理")
        if scan["pending_writes"] or state["pending_writes"]:
            raise RuntimeError("存在未核实写入，先只读核对，不推进检查或写入")

    def get(self, wid):
        """Read the complete current work item."""
        return self.cli(
            "workitem",
            "get",
            "--project-key",
            self.c["space"],
            "--work-item-id",
            str(wid),
            "--fields",
            "_all",
            "--auto-paginate",
        )

    def existing(self):
        """Search both defects and requirements, then refresh mapped items."""
        spaces = self.cli("project", "search", "--project-key", self.c["space"])[
            "projects"
        ]
        space = next(
            p["project_key"] for p in spaces if p["simple_name"] == self.c["space"]
        )
        result = []
        for kind, label, fields in [
            ("issue", "缺陷", ["缺陷名称", "复现步骤", "实际结果", "期望结果"]),
            ("story", "需求", ["需求名称", "需求描述"]),
        ]:
            columns = ", ".join("`" + f + "`" for f in ["工作项id", *fields])
            terms = [
                term.replace("'", "''").replace("%", r"\%").replace("_", r"\_")
                for term in self.c["dedupe_terms"]
            ]
            where = " OR ".join(
                f"`{field}` like '%{term}%'" for field in fields for term in terms
            )
            data = self.cli(
                "workitem",
                "query",
                "--project-key",
                self.c["space"],
                "--mql",
                f"SELECT {columns} FROM `{space}`.`{label}` WHERE {where}",
                "--auto-paginate",
            )
            rows = [r for group in (data.get("data") or {}).values() for r in group]
            if sum(g.get("count", 0) for g in (data.get("list") or [])) > len(rows):
                raise RuntimeError("Meegle 查询未返回完整分页，停止查重与写入")
            for raw_row in rows:
                row = {
                    f["key"]: next(iter(f.get("value", {}).values()), "")
                    for f in raw_row["moql_field_list"]
                }
                result.append(
                    {"id": int(row["work_item_id"]), "type": kind, "fields": row}
                )
        # Refresh tracked records even when humans have changed their titles.
        for tracked in self.state()["tracked_issues"]:
            item = self.get(tracked["work_item_id"])
            result = [r for r in result if r["id"] != tracked["work_item_id"]]
            result.append(
                {
                    "id": tracked["work_item_id"],
                    "type": item["work_item_attribute"]["work_item_type"]["key"],
                    "name": item["work_item_attribute"]["work_item_name"],
                    "status": item["work_item_attribute"]["work_item_status"]["name"],
                    "fields": values(item),
                }
            )
        return result

    def collect(self):
        """Collect full context but flag only recent or changed feedback."""
        state = self.state()
        now = datetime.now(UTC)
        issues = []
        for repo in self.c["repositories"]:
            items = self.github(
                f"repos/{repo}/issues?state=all&sort=created&direction=asc&per_page=100"
            )
            for item in items:
                if "pull_request" in item:
                    continue
                number = item["number"]
                comments = self.github(
                    f"repos/{repo}/issues/{number}/comments?per_page=100"
                )
                if len(comments) != item["comments"]:
                    raise RuntimeError(
                        f"{repo}#{number} 评论数量变化或分页不完整，请重新采集"
                    )
                issue = {
                    "key": f"github-{repo.replace('/', '-')}-issue-{number}",
                    "repository": repo,
                    "number": number,
                    "title": item["title"],
                    "state": item["state"],
                    "state_reason": item["state_reason"],
                    "id": item["id"],
                    "url": item["html_url"],
                    "body": item["body"] or "",
                    "author": item["user"]["login"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "comments": [
                        {
                            "id": comment["id"],
                            "url": comment["html_url"],
                            "body": comment["body"] or "",
                            "author": comment["user"]["login"],
                            "created_at": comment["created_at"],
                            "updated_at": comment["updated_at"],
                        }
                        for comment in comments
                    ],
                }
                issues.append(issue)
        versions = {issue["key"]: fingerprint(issue) for issue in issues}
        posts = source_index(issues)
        source_versions = {
            url: fingerprint({k: v for k, v in post.items() if k != "comments"})
            for url, post in posts.items()
        }
        old = state.get("observed_issue_versions", {})
        cutoff = now - timedelta(days=self.c["initial_days"])
        changed = []
        for issue in issues:
            recent = (
                max(
                    datetime.fromisoformat(post["updated_at"])
                    for post in [issue, *issue["comments"]]
                )
                >= cutoff
            )
            if (state.get("last_successful_check_at") or recent) and old.get(
                issue["key"]
            ) != versions[issue["key"]]:
                changed.append(issue["key"])
        old_sources = state.get("observed_source_versions", {})
        changed_urls = [
            url
            for url, version in source_versions.items()
            if old_sources.get(url) != version
            and any(
                issue["key"] in changed and url.split("#")[0] == issue["url"]
                for issue in issues
            )
        ]
        changed_urls.extend(url for url in old_sources if url not in source_versions)
        return {
            "config_fingerprint": self.config_fingerprint,
            "collected_at": now.isoformat(),
            "base_checkpoint": state.get("last_successful_check_at"),
            "changed_issue_keys": changed,
            "changed_source_urls": changed_urls,
            "observed_issue_versions": versions,
            "observed_source_versions": source_versions,
            "weekly_review": now.astimezone(ZoneInfo(self.c["timezone"])).weekday()
            == self.c["review_weekday"],
            "issues": issues,
            "tracked_issues": state["tracked_issues"],
            "existing": self.existing(),
            "pending_writes": state["pending_writes"],
        }

    def resolve(self):
        """Resolve and verify destination metadata before writing."""
        c = self.c
        fields = self.cli(
            "workitem",
            "meta-fields",
            "--project-key",
            c["space"],
            "--work-item-type",
            c["work_item_type"],
        )["list"]
        fields = {f["field_key"]: f for f in fields}
        required = self.cli(
            "workitem",
            "meta-create-fields",
            "--project-key",
            c["space"],
            "--work-item-type",
            c["work_item_type"],
        )["FieldConfList"]
        self.cli(
            "workitem",
            "meta-roles",
            "--project-key",
            c["space"],
            "--work-item-type",
            c["work_item_type"],
        )
        for key, field in c["fields"].items():
            if field not in fields:
                raise ValueError("字段配置已变化：" + key)
        for kind in ["project", "product"]:
            attr = self.get(c[kind]["id"])["work_item_attribute"]
            if (
                attr["work_item_name"] != c[kind]["name"]
                or attr["work_item_type"]["name"] != c[kind]["type"]
            ):
                raise ValueError("目标不匹配：" + kind)
            if attr["owned_project"]["simple_name"] != c["space"]:
                raise ValueError("目标不在指定空间")
            relation = fields[c["fields"][kind]].get("related_work_item_info", [])
            if not any(
                r["work_item_type"] == attr["work_item_type"]["key"] for r in relation
            ):
                raise ValueError("关联字段的对端类型变化")

        def option(key, name):
            opts = [
                o
                for o in fields[key].get("option", [])
                if o["option_name"].strip() == name and not o.get("disabled")
            ]
            if len(opts) != 1:
                raise ValueError("选项不唯一：" + name)
            return opts[0]["option_id"]

        template = option("template", c["template"]["name"])
        if str(template) != str(c["template"]["id"]):
            raise ValueError("模板已变化")
        people = self.cli("user", "search", "--user-keys", c["operator"])
        people = [
            p
            for p in people
            if p.get("name_cn") == c["operator"] and p.get("status") == "activated"
        ]
        if len(people) != 1:
            raise ValueError("经办人不唯一或不可用")
        base = {
            "template": str(template),
            "issue_reporter": [self.cli("user", "me")["user_key"]],
            "issue_operator": [people[0]["user_key"]],
            "priority": option("priority", c["priority"]),
            c["fields"]["board"]: [
                {"option_id": option(c["fields"]["board"], c["board"])}
            ],
            c["fields"]["project"]: [c["project"]["id"]],
            c["fields"]["product"]: [c["product"]["id"]],
        }
        known = set(base) | set(c["fields"].values())
        if any(
            f["field_key"] not in known for f in required if f.get("is_required") == 1
        ):
            raise ValueError("出现未配置的必填字段")
        return base

    def sources(self, scan, draft):
        """Resolve draft citations only against collected source URLs."""
        self.validate_scan(scan)
        posts = source_index(scan["issues"])
        if not draft.get("sources"):
            raise ValueError("缺少原帖来源")
        urls, lines = [], []
        for src in draft["sources"]:
            url = src["url"]
            post = posts[url]
            if not src.get("summary", "").strip():
                raise ValueError("原帖链接需要事件摘要")
            urls.append(url)
            date = post["created_at"][:10]
            if post["updated_at"] != post["created_at"]:
                date += f"（更新于 {post['updated_at'][:10]}）"
            lines.append(f"- {date}：[{src['summary']}]({url})")
        return urls, "\n".join(lines)

    def matches(self, records, draft):
        """Match issue-level URLs and stable local mappings across repositories."""
        roots = {src["url"].split("#")[0] for src in draft["sources"]}
        pattern = r"https://github\.com/[^/\s]+/[^/\s]+/issues/\d+(?!\d)"
        found = [
            record
            for record in records
            if roots.intersection(
                re.findall(pattern, json.dumps(record, ensure_ascii=False))
            )
        ]
        for item in self.state()["tracked_issues"]:
            if item["source_key"] == draft["source_key"] and not any(
                r["id"] == item["work_item_id"] for r in found
            ):
                found.extend(r for r in records if r["id"] == item["work_item_id"])
        return found

    def publish(self, scan, draft, apply=False):
        """Preview or apply one factual create or append operation."""
        mode = draft.get("mode", "create")
        allowed = {
            "mode",
            "source_key",
            "sources",
            "title",
            "steps",
            "expected",
            "actual",
            "work_item_id",
            "progress",
        }
        if (
            set(draft) - allowed
            or mode not in ["create", "append"]
            or not draft.get("source_key")
        ):
            raise ValueError("只支持新建或追加事实进展")
        urls, source_text = self.sources(scan, draft)
        base = self.resolve()
        records = self.existing()
        matches = self.matches(records, draft)
        field = self.c["fields"]["actual"]
        wid, before = draft.get("work_item_id"), None
        if mode == "create":
            if wid:
                raise ValueError("新建不能指定已有工作项")
            if matches:
                return {"status": "existing", "matches": matches, "writes": 0}
            for key in ["title", "steps", "expected", "actual"]:
                if not draft.get(key, "").strip():
                    raise ValueError("缺少字段：" + key)
            fields = {
                **base,
                self.c["fields"]["name"]: self.c["title_prefix"] + " " + draft["title"],
                self.c["fields"]["steps"]: spaced_text(draft["steps"]),
                self.c["fields"]["expected"]: spaced_text(draft["expected"]),
                field: spaced_text(draft["actual"] + "\n\n原帖记录")
                + "\n\n"
                + source_text,
            }
        else:
            if not wid or not draft.get("progress", "").strip():
                raise ValueError("追加需要目标缺陷和事实进展")
            before = self.get(wid)
            attr = before["work_item_attribute"]
            if attr["work_item_type"]["key"] != "issue" or {
                r["id"] for r in matches
            } != {wid}:
                raise ValueError(
                    "只追加唯一匹配的 HA 缺陷，不自动迁移需求或归并多个条目"
                )
            if attr["owned_project"]["simple_name"] != self.c["space"]:
                raise ValueError("目标缺陷不在指定空间")
            if not any(
                x["id"] == self.c["project"]["id"]
                for x in values(before).get(self.c["fields"]["project"], [])
            ):
                raise ValueError("目标缺陷未关联配置中的项目")
            current = values(before).get(field) or ""
            if all(url in current for url in urls) and normalized(
                draft["progress"]
            ) in normalized(current):
                return {"status": "unchanged", "work_item_id": wid, "writes": 0}
            fields = {
                field: spaced_text(current, existing=True)
                + "\n\n\\\n"
                + spaced_text(draft["progress"])
                + "\n\n"
                + source_text
            }
        plan = {
            "status": "preview",
            "mode": mode,
            "work_item_id": wid,
            "fields": fields,
            "writes": 0,
        }
        if not apply:
            return plan
        with locked(self.path):
            self.validate_scan(scan)
            state = self.state()
            pending = state.setdefault("pending_writes", [])
            if pending:
                raise RuntimeError(
                    "存在未核实写入，先只读核对并处理 pending_writes，禁止自动重试"
                )
            if mode == "create" and self.matches(self.existing(), draft):
                return {"status": "existing", "writes": 0}
            if before and values(self.get(wid)) != values(before):
                raise RuntimeError("预览后远端内容发生变化，停止覆盖")
            record = {
                "source_key": draft["source_key"],
                "work_item_id": wid,
                "mode": mode,
                "sources": urls,
                "fields": fields,
                "started_at": datetime.now(UTC).isoformat(),
            }
            pending.append(record)
            save(self.path, state)
            args = [
                "workitem",
                "create" if mode == "create" else "update",
                "--project-key",
                self.c["space"],
            ]
            args += (
                ["--work-item-type", "issue"]
                if mode == "create"
                else ["--work-item-id", str(wid)]
            )
            for key, value in fields.items():
                encoded = (
                    value
                    if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False)
                )
                args += [
                    "--fields",
                    json.dumps(
                        {"field_key": key, "field_value": encoded}, ensure_ascii=False
                    ),
                ]
            result = self.cli(
                *args
            )  # On any exception, pending journal remains intact.
            wid = result["work_item_id"] if mode == "create" else wid
            record["work_item_id"] = wid
            save(self.path, state)
            after = self.get(wid)
            self.verify(after, fields, base if mode == "create" else None)
            tracked = state.setdefault("tracked_issues", [])
            entry = next(
                (x for x in tracked if x["source_key"] == draft["source_key"]), None
            )
            if entry is None:
                entry = {"source_key": draft["source_key"]}
                tracked.append(entry)
            entry.update(
                work_item_id=wid,
                work_item_type="issue",
                source_urls=sorted(set(entry.get("source_urls", [])) | set(urls)),
                remote_status=after["work_item_attribute"]["work_item_status"]["name"],
            )
            pending.remove(record)
            save(self.path, state)
            return {
                "status": "verified",
                "work_item_id": wid,
                "writes": 1,
                "url": f"https://project.feishu.cn/{self.c['space']}/issue/detail/{wid}",
            }

    def verify(self, item, fields, base):
        """Verify written content and configured ownership from readback."""
        actual = values(item)
        actual["name"] = item["work_item_attribute"]["work_item_name"]
        for key in [
            self.c["fields"][x] for x in ["name", "steps", "expected", "actual"]
        ]:
            if key in fields and normalized(actual.get(key) or "") != normalized(
                fields[key]
            ):
                raise RuntimeError("读回内容不一致：" + key)
            if key in fields:
                links = re.findall(r"https://github\.com/[^\s)<>]+", fields[key])
                if any(url not in (actual.get(key) or "") for url in links):
                    raise RuntimeError("读回来源链接缺失：" + key)
        if item["work_item_attribute"]["work_item_type"]["key"] != "issue":
            raise RuntimeError("读回类型不是缺陷")
        if base:
            for kind in ["project", "product"]:
                if [x["id"] for x in actual.get(self.c["fields"][kind], [])] != base[
                    self.c["fields"][kind]
                ]:
                    raise RuntimeError("读回归属不一致")
            if [x["value"] for x in actual.get(self.c["fields"]["board"], [])] != [
                x["option_id"] for x in base[self.c["fields"]["board"]]
            ]:
                raise RuntimeError("读回板块不一致")
            if str(actual.get("priority", {}).get("value")) != str(base["priority"]):
                raise RuntimeError("读回优先级不一致")
            for role, key in [
                ("经办人", "issue_operator"),
                ("报告人", "issue_reporter"),
            ]:
                people = [
                    m["key"]
                    for r in item["work_item_attribute"]["role_members"]
                    if r["name"] == role
                    for m in r.get("members", [])
                ]
                if people != base[key]:
                    raise RuntimeError("读回人员不一致：" + role)

    def finish(self, scan):
        """Save a checkpoint only after the operator has handled every change."""
        with locked(self.path):
            self.validate_scan(scan)
            state = self.state()
            if state.get("last_successful_check_at", "") >= scan["collected_at"]:
                raise ValueError("不能用旧快照回退检查进度")
            state.update(
                last_successful_check_at=scan["collected_at"],
                observed_issue_versions=scan["observed_issue_versions"],
                observed_source_versions=scan["observed_source_versions"],
            )
            save(self.path, state)
            return {"status": "checkpoint_saved", "remote_writes": 0}


def main():
    """Dispatch collection, preview, write, or checkpoint commands."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config.json",
    )
    parser.add_argument("--state", type=Path, help="本地运行状态路径；不存进仓库")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser(
        "collect", help="只读采集 Issues、评论和飞书条目，输出检查快照"
    )
    collect.add_argument("--out", required=True, type=Path)
    publish = sub.add_parser("publish", help="默认预览单条；--apply 才执行远端写入")
    publish.add_argument("--scan", required=True, type=Path)
    publish.add_argument("--draft", required=True, type=Path)
    publish.add_argument("--apply", action="store_true")
    finish = sub.add_parser("finish", help="判断与写入全部处理完后保存本次检查进度")
    finish.add_argument("--scan", required=True, type=Path)
    args = parser.parse_args()
    config = load(args.config)
    state = (
        args.state
        or Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        / config["state_file"]
    )
    flow = Intake(config, state)
    if args.command == "collect":
        result = flow.collect()
        save(args.out, result)
        result = {
            "snapshot": str(args.out),
            "issues": len(result["issues"]),
            "changed": len(result["changed_issue_keys"]),
            "existing": len(result["existing"]),
        }
    elif args.command == "publish":
        result = flow.publish(load(args.scan), load(args.draft), args.apply)
    else:
        result = flow.finish(load(args.scan))
    print(json.dumps(result, ensure_ascii=False, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
