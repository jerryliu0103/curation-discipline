#!/usr/bin/env python3
"""PreToolUse/Bash hook：指令碰到錯誤的資料源時，停下來問過人再說。

這支要解決的問題

    某個專案把正本資料庫搬到伺服器上，本機留了一份舊副本。「絕不可以用本機舊副本」
    這條規則寫下來了，然後被安靜地忽略了一個月——查核時發現五個代理定義檔全都還指著
    那份舊副本。

    沒有人粗心。這條規則沒有牙齒：讀舊副本會拿到看起來很合理的舊資料，寫舊副本會成功，
    **而且兩者都不會報錯**。一條違反了也沒有回饋的規則，不是規則。

    這支把它變成一件會停下來問的事。

用 ask，不用 deny

    下面每一條路徑都有正當用途——離線查閱、拿可拋棄的副本試跑一批資料。擋死會讓人
    繞過去，然後你就完全失去可見度了。要的是「不會不小心走進去」，不是「不准走到這裡」。

為什麼是 hook 不是 permission 規則

    Bash 的 permission 規則是比對指令**前綴**。真實的指令幾乎都是複合的——
    `cd x && psql ...`——前綴接不住，規則就不會觸發。settings 的規則對簡單情形是有用的
    補強，真正的攔截在這裡。

請設定我

    把下面的 PATTERNS 改成你自己專案的陷阱。出貨時附一組永遠不會命中的佔位樣式會讓
    這支檔案變成裝飾品，所以下面的例子是真的樣式——**重點是形狀，不是那幾個字串**。

    請保留 sys.stdout.reconfigure 那一行。一支在非 UTF-8 主控台丟 UnicodeEncodeError
    的 hook 會以非 0 離開、且沒有輸出任何決定，而 PreToolUse 把那視為「沒有意見」——
    於是 guard 一邊 fail open 一邊看起來運作正常。
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# （編譯後的樣式, 給人看的理由）
#
# 請換成你自己專案的陷阱。下面三種形狀涵蓋了實務上大部分會出事的情況：
#   1. 一個仍然指著已被取代的資料源的環境變數
#   2. 一個讓腳本可以退回本機副本的逃生門旗標
#   3. 一個關掉連線檢查的環境變數覆寫
PATTERNS = [
    (
        re.compile(r'(psql|pg_dump|pg_restore|mysql|sqlite3)\b[^|;&]*"?\$STALE_DB_URL"?'),
        "直接用了 $STALE_DB_URL。那個變數指向一份已被取代的本機副本："
        "讀出來是舊快照、寫進去不會到正本，**而且兩種情況都不會報錯**。"
        "請改用解析出正本連線字串的方式。",
    ),
    (
        re.compile(r"--allow-local\b"),
        "帶了 --allow-local：這會讓腳本在連不到正本時退回本機副本。",
    ),
    (
        re.compile(r"\bDB_ALLOW_LOCAL\s*=\s*1\b"),
        "設了 DB_ALLOW_LOCAL=1：這會關掉連線檢查並允許退回本機副本。",
    ),
]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""

    for pattern, reason in PATTERNS:
        if pattern.search(command):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": (
                                "⚠ 這個指令會碰到錯誤的資料源：" + reason
                            ),
                        }
                    },
                    ensure_ascii=False,
                )
            )
            sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
