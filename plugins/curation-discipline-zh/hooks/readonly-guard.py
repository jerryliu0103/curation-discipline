#!/usr/bin/env python3
"""PreToolUse/Bash hook：擋掉任何不是唯讀的資料庫指令。

掛給絕對不能寫入的代理（validator、reader）。它們的 frontmatter 已經拿掉 Write 與
Edit，但那管不到 Bash——而 Bash 正是資料庫真正被寫入的那條路。這支補的就是那個缺口。

用 deny 不用 ask：一個職責就是驗證的代理沒有任何正當理由要寫入，沒有什麼好商量。
有正當用途的那些路徑請用 canonical-store-guard.py。

為什麼是 Python 不是一行 shell
    最直覺的版本是三行 bash 加 jq。它會一直正常，直到跑在一台沒有 jq 的機器上——
    然後它會以非 0 離開、且沒有輸出任何決定，而 PreToolUse 收到這種結果就是放行。
    **一支 fail open 的 guard，跟一支正常運作的 guard 看起來一模一樣。**
    Python 3 在每個平台上都已經是 Claude Code 工具鏈的前提，jq 不是。

為什麼下面那行 UTF-8 reconfigure 不能刪
    不是裝飾。曾經有一支 hook 在主控台編碼不是 UTF-8 的機器上印出非 ASCII 字元，
    丟 UnicodeEncodeError、以非 0 離開、stdout 什麼都沒有，於是**安靜地停止攔截
    任何東西**。是靠手動把測資 pipe 進去才發現的——三個該被擋的指令全部放行。
    你如果要改下面的訊息，請保留這一行。
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 會修改資料或結構的敘述。用單字邊界，才不會被 created_at、updated_at 這種欄位名誤觸。
WRITE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER)\b",
    re.IGNORECASE,
)

# Shell 導向輸出到檔案。唯讀代理該把發現寫在回覆裡，不是寫到某個檔案去。
WRITE_SHELL = re.compile(r"(^|\s)(>|>>)\s*\S", re.MULTILINE)

# 這裡「不剝除引號內容」，而且是刻意的。
#
# 直覺的優化是先把引號裡的字串剝掉，這樣
#     SELECT * FROM logs WHERE note LIKE '%DELETE%'
# 就不會被誤判成寫入。自我測試抓到了這樣為什麼是錯的：SQL 是**包在引號裡**送給 psql
# 的——`psql -c "INSERT INTO ..."`——所以剝除引號區段等於把敘述本身剝掉，guard 於是
# 放行每一個寫入，同時回報一切正常。
# 那個 bug 只存活了一次測試執行，而這正是為什麼 test_hooks.py 要跟這支檔案一起出貨。
#
# 所以這支直接比對原始指令，寧可過度攔截。唯讀代理偶爾被擋下一個字面值裡含有 DELETE
# 的 SELECT，只是小麻煩；唯讀代理安靜地放行寫入，才是這支檔案存在要防的事。
# **guard 一定要錯的時候，要往「吵」的方向錯。**


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # 讀不到輸入不該讓正常工作失敗。注意這是一條 fail open 的路徑：
        # 之所以可接受，是因為 payload 壞掉代表這次根本不是真的工具呼叫。
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command:
        sys.exit(0)

    hit = WRITE_SQL.search(command)
    if hit:
        print(
            "已阻擋：這個代理是唯讀的。指令裡出現 "
            f"'{hit.group(0).upper()}'。唯讀代理只能執行 SELECT；"
            "寫入屬於流水線中由人核准的那一步。",
            file=sys.stderr,
        )
        sys.exit(2)

    if WRITE_SHELL.search(command):
        print(
            "已阻擋：這個代理是唯讀的，而這個指令把輸出導向檔案。"
            "請把結果寫在你的回覆裡，不要寫進檔案。",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
