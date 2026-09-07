#!/usr/bin/env python3
"""兩支 guard 的對抗式自我測試。執行方式：python hooks/test_hooks.py

這個檔案存在的理由是 silent-failure-hunting 第 5 條：**一支還沒印出決定就死掉的 guard
會 fail open，而且看起來跟一支正常運作的 guard 一模一樣。** 要知道一支 guard 有沒有
真的擋住它宣稱會擋的東西，唯一的方法就是把那些輸入餵給它、然後對結果做斷言。

不需要 pytest、沒有任何相依套件——所以沒有不跑它的藉口。
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
READONLY = HERE / "readonly-guard.py"
CANONICAL = HERE / "canonical-store-guard.py"

BLOCK = "block"      # 離開碼 2，訊息在 stderr
ASK = "ask"          # 離開碼 0，stdout 帶 permissionDecision=ask
ALLOW = "allow"      # 離開碼 0，沒有輸出

CASES = [
    # (要測的 hook, 指令, 預期結果)
    (READONLY, 'psql "$DB" -c "SELECT * FROM items LIMIT 5"', ALLOW),
    (READONLY, 'psql "$DB" -c "INSERT INTO items VALUES (1)"', BLOCK),
    (READONLY, 'psql "$DB" -c "delete from items"', BLOCK),
    (READONLY, 'cd /project && psql "$DB" -c "UPDATE items SET x=1"', BLOCK),
    (READONLY, 'psql "$DB" -c "DROP TABLE items"', BLOCK),
    (READONLY, 'psql "$DB" -c "SELECT created_at, updated_at FROM items"', ALLOW),
    # 刻意的誤判：字面值裡含有寫入關鍵字的 SELECT 會被擋。
    # 為了避免這個而去剝除引號區段，會讓整支 guard 失效——見 readonly-guard.py 裡
    # WRITE_SQL 上面那段註解。**過度攔截是正確的犯錯方向。**
    (READONLY, "psql \"$DB\" -c \"SELECT * FROM logs WHERE note LIKE '%DELETE%'\"", BLOCK),
    (READONLY, 'psql "$DB" -c "SELECT 1" > /tmp/out.txt', BLOCK),
    (READONLY, "ls -la", ALLOW),
    (CANONICAL, 'psql "$STALE_DB_URL" -c "SELECT 1"', ASK),
    (CANONICAL, "node scripts/sync.js --allow-local", ASK),
    (CANONICAL, "DB_ALLOW_LOCAL=1 node server.js", ASK),
    (CANONICAL, 'psql "$DB_URL" -c "SELECT 1"', ALLOW),
]


def run(hook: Path, command: str):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode == 2:
        return BLOCK, proc.stderr.strip()
    if proc.returncode != 0:
        return f"crashed({proc.returncode})", (proc.stderr or "").strip()
    out = proc.stdout.strip()
    if not out:
        return ALLOW, ""
    try:
        decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "malformed", out
    return decision, out


def main() -> int:
    failures = 0
    for hook, command, expected in CASES:
        got, detail = run(hook, command)
        ok = got == expected
        if not ok:
            failures += 1
        print(f"{'PASS' if ok else 'FAIL'}  {hook.name:26} 預期={expected:6} 實際={got:10} {command}")
        if not ok and detail:
            print(f"      -> {detail}")
    print()
    if failures:
        print(f"{len(CASES)} 個案例中有 {failures} 個失敗。")
        print("一支擋不住它宣稱會擋的東西的 guard，比沒有 guard 更糟：")
        print("它是一支所有人都相信的 guard。")
        return 1
    print(f"{len(CASES)} 個案例全部通過。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
