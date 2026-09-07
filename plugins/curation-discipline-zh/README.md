# curation-discipline-zh

別讓 AI 代理安靜地把你的資料庫弄髒。

完整說明：[repo README](../../README.zh-TW.md) 與 [docs/why.zh-TW.md](../../docs/why.zh-TW.md)。

## 一條規則

> **代理不寫正本。代理寫 staging。由人把 staging 搬進正本。**

## 內容

| | |
|---|---|
| **代理** | `curator`、`validator`、`reader`、`mirror-writer`、`principle-extractor` |
| **Skills** | `curation-pipeline`、`silent-failure-hunting`、`provenance-and-dedup` |
| **Hooks** | `readonly-guard.py`、`canonical-store-guard.py`、`test_hooks.py` |
| **範本** | `CLAUDE.md.template`、`settings.json.example`、`staging-record.schema.json` |

## 裝好之後

**1. 跑 guard 的測試。**

```bash
python hooks/test_hooks.py
```

**2. 把 `canonical-store-guard.py` 指向你自己的陷阱。** 出貨時它的 `PATTERNS` 是範例
字串，**在你的專案裡不會命中任何東西**。改成那些會連到錯誤資料源、**而且不會報錯**的
指令與變數——那些才是值得守的。

**3. 把 `templates/CLAUDE.md.template` 複製進你的專案**，填上正本、staging 位置、
以及陷阱。事故那一段先留空，它會自己長出來。

## English

英文版是 `curation-discipline`。內容相同，**裝一個就好，不要兩個都裝**。
