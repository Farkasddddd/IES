import argparse
import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = REPO_ROOT / "project_metadata" / "update_history"
DB_PATH = DB_DIR / "update_history.db"
JSON_PATH = DB_DIR / "update_history_latest.json"
MD_PATH = DB_DIR / "update_history_latest.md"


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    return completed.stdout.rstrip("\r\n")


def current_branch() -> str:
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"])


def current_status() -> str:
    return run_git(["status", "-sb"])


def current_origin_head() -> str | None:
    try:
        return run_git(["rev-parse", "origin/main"])
    except subprocess.CalledProcessError:
        return None


def commit_on_origin(commit_hash: str) -> int:
    try:
        output = run_git(["branch", "-r", "--contains", commit_hash])
    except subprocess.CalledProcessError:
        return 0
    return 1 if "origin/main" in output else 0


def commit_files(commit_hash: str) -> list[str]:
    output = run_git(["show", "--pretty=", "--name-only", commit_hash])
    return [line.strip() for line in output.splitlines() if line.strip()]


def collect_commits(limit: int | None = None) -> list[dict]:
    pretty = "%H%x1f%cI%x1f%an%x1f%ae%x1f%s%x1f%b%x1e"
    args = ["log", f"--pretty=format:{pretty}"]
    if limit is not None:
        args.append(f"-n{limit}")
    raw = run_git(args)
    branch = current_branch()
    origin_head = current_origin_head()
    records: list[dict] = []

    for chunk in raw.split("\x1e"):
        if not chunk:
            continue
        chunk = chunk.strip("\r\n")
        if not chunk:
            continue
        parts = chunk.split("\x1f")
        if len(parts) < 6:
            continue
        commit_hash, committed_at, author_name, author_email, subject, body = parts[:6]
        files = commit_files(commit_hash)
        body = body.strip()
        content_summary = subject if not body else f"{subject}\n{body}"
        records.append(
            {
                "commit_hash": commit_hash,
                "committed_at": committed_at,
                "author_name": author_name,
                "author_email": author_email,
                "branch_name": branch,
                "subject": subject,
                "body": body,
                "content_summary": content_summary,
                "changed_files_json": json.dumps(files, ensure_ascii=False),
                "changed_file_count": len(files),
                "is_on_origin_main": commit_on_origin(commit_hash),
                "origin_head_when_synced": origin_head,
            }
        )
    return records


def ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commit_hash TEXT NOT NULL UNIQUE,
            committed_at TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_email TEXT NOT NULL,
            branch_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT,
            content_summary TEXT NOT NULL,
            changed_files_json TEXT NOT NULL,
            changed_file_count INTEGER NOT NULL,
            is_on_origin_main INTEGER NOT NULL DEFAULT 0,
            origin_head_when_synced TEXT,
            recorded_at TEXT NOT NULL
        )
        """
    )


def upsert_records(conn: sqlite3.Connection, records: list[dict]):
    recorded_at = datetime.now().astimezone().isoformat(timespec="seconds")
    for record in records:
        conn.execute(
            """
            INSERT INTO project_updates (
                commit_hash,
                committed_at,
                author_name,
                author_email,
                branch_name,
                subject,
                body,
                content_summary,
                changed_files_json,
                changed_file_count,
                is_on_origin_main,
                origin_head_when_synced,
                recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(commit_hash) DO UPDATE SET
                committed_at=excluded.committed_at,
                author_name=excluded.author_name,
                author_email=excluded.author_email,
                branch_name=excluded.branch_name,
                subject=excluded.subject,
                body=excluded.body,
                content_summary=excluded.content_summary,
                changed_files_json=excluded.changed_files_json,
                changed_file_count=excluded.changed_file_count,
                is_on_origin_main=excluded.is_on_origin_main,
                origin_head_when_synced=excluded.origin_head_when_synced,
                recorded_at=excluded.recorded_at
            """,
            (
                record["commit_hash"],
                record["committed_at"],
                record["author_name"],
                record["author_email"],
                record["branch_name"],
                record["subject"],
                record["body"],
                record["content_summary"],
                record["changed_files_json"],
                record["changed_file_count"],
                record["is_on_origin_main"],
                record["origin_head_when_synced"],
                recorded_at,
            ),
        )


def export_latest(conn: sqlite3.Connection, limit: int):
    rows = conn.execute(
        """
        SELECT
            commit_hash,
            committed_at,
            author_name,
            author_email,
            branch_name,
            subject,
            body,
            content_summary,
            changed_files_json,
            changed_file_count,
            is_on_origin_main,
            origin_head_when_synced,
            recorded_at
        FROM project_updates
        ORDER BY committed_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    items = []
    for row in rows:
        items.append(
            {
                "commit_hash": row[0],
                "committed_at": row[1],
                "author_name": row[2],
                "author_email": row[3],
                "branch_name": row[4],
                "subject": row[5],
                "body": row[6],
                "content_summary": row[7],
                "changed_files": json.loads(row[8]),
                "changed_file_count": row[9],
                "is_on_origin_main": bool(row[10]),
                "origin_head_when_synced": row[11],
                "recorded_at": row[12],
            }
        )

    JSON_PATH.write_text(json.dumps({"updates": items}, ensure_ascii=False, indent=2), encoding="utf-8")

    status = current_status()
    lines = [
        "# 项目更新记录",
        "",
        f"- 当前分支状态：`{status}`",
        f"- 数据库文件：`{DB_PATH.relative_to(REPO_ROOT)}`",
        f"- 导出时间：`{datetime.now().astimezone().isoformat(timespec='seconds')}`",
        "",
        "## 最近更新",
        "",
    ]
    for item in items:
        lines.extend(
            [
                f"### {item['subject']}",
                "",
                f"- 提交哈希：`{item['commit_hash']}`",
                f"- 提交时间：`{item['committed_at']}`",
                f"- 记录时间：`{item['recorded_at']}`",
                f"- 作者：`{item['author_name']} <{item['author_email']}>`",
                f"- 分支：`{item['branch_name']}`",
                f"- 已在远端主分支：`{'是' if item['is_on_origin_main'] else '否'}`",
                f"- 变更文件数：`{item['changed_file_count']}`",
                f"- 更新内容：{item['content_summary'].replace(chr(10), ' / ')}",
                "",
            ]
        )
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Sync git commit history into a local SQLite update database.")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        records = collect_commits(limit=args.limit)
        upsert_records(conn, records)
        conn.commit()
        export_latest(conn, limit=args.limit)
    finally:
        conn.close()

    print(f"db_path={DB_PATH}")
    print(f"json_path={JSON_PATH}")
    print(f"md_path={MD_PATH}")
    print(f"records_synced={len(records)}")


if __name__ == "__main__":
    main()
