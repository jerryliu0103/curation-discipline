# curation-discipline

**別讓 AI 代理安靜地把你的資料庫弄髒。**

English: [README.md](README.md)

一個 Claude Code plugin：五個代理、三支 skill、兩支經過對抗測試的 hook，以及一份
「不會報錯的失敗」清單。

---

## 問題

你把代理指向資料庫，請它幫你建一份資料集。它做了，列也長出來了。幾個月後你發現：
同一個東西以兩個名字存在兩筆、某一批資料沒有來源、某個同步從一次 schema 變更之後
就一直在發布過期的鏡像，而沒有人把兩件事連在一起。

**這些全部都沒有報錯。** 那才是真正的問題——不是代理會犯錯，而是**它犯的是安靜的那
一種**。程式當掉會告訴你在哪一行、什麼時候；一個什麼都沒配對到的 JOIN 什麼都不會
說，等你發現的時候，壞掉的列跟好的列已經長得一模一樣了。

## 這是什麼

一條規則，以及讓人繞不過去的那些機制：

> **代理不寫正本。代理寫 staging。由人把 staging 搬進正本。**

```
   蒐集              檢查              核准             寫入
  ──────            ──────            ──────           ──────
  curator     →    validator     →     人        →      人
  （只寫            （唯讀，由        （讀差異）      （執行 SQL）
   staging）         hook 強制）
```

staging 檔案就是那份可供審查的東西。它是「代理加了 40 筆」與「這裡有 40 筆，其中 3 筆
需要你看一下，理由如下」之間的差別。

## 安裝

```bash
/plugin marketplace add jerryliu0103/curation-discipline
```

```bash
/plugin install curation-discipline-zh@curation-discipline
```

英文版是 `curation-discipline@curation-discipline`。內容與結構相同，**裝一個就好，
不要兩個都裝**。

## 內容

### 代理

| 代理 | 職責 | 可以寫 |
|---|---|---|
| `curator` | 蒐集與正規化來源材料 | 只有 staging |
| `validator` | 在資料進入正本前檢查一整批 | **什麼都不能寫** |
| `reader` | 從正本回答問題 | **什麼都不能寫** |
| `mirror-writer` | 單向發布到人類可讀的鏡像 | 只有鏡像 |
| `principle-extractor` | 從訪談材料裡分離方法與個人喜好 | 只有 staging |

### Skills

- **`curation-pipeline`**——staging 閘門、四個階段、為什麼強制必須是結構性的，
  以及試跑的兩件不明顯的事。
- **`silent-failure-hunting`**——十個真實發生、而且沒有產生任何錯誤訊息的失敗，
  各自的代價與現在靠什麼抓。**就算你不裝這個 plugin，這一支也值得讀。**
- **`provenance-and-dedup`**——為什麼比對文字抓不到重複匯入、該用什麼座標比對、
  雙向核對，以及刻意丟棄清單。

### Hooks

- `readonly-guard.py`——擋掉唯讀代理的非唯讀指令。`disallowedTools` 管不到 `Bash`，
  而 `Bash` 正是資料庫真正被寫入的那條路。
- `canonical-store-guard.py`——指令碰到已被取代的資料源時停下來問。
  `PATTERNS` 要改成你自己專案的陷阱。
- `test_hooks.py`——**請執行它。** 兩支 guard、十三個對抗案例、零相依套件。

```bash
python hooks/test_hooks.py
```

這支測試在**第一次執行時就抓到 `readonly-guard.py` 的真實錯誤**：原本為了避免誤判而
去剝除引號內容，結果把 SQL 本身剝掉了——因為 `psql -c "INSERT ..."` 的語句正是包在
引號裡。四個該被擋的指令全部放行，而 guard 看起來完全正常。**這正是這個 plugin 在講
的失敗模式，而它就發生在寫這個 plugin 的過程中。**

### 範本

`CLAUDE.md.template`、`settings.json.example`、`staging-record.schema.json`。

## 用結構強制，不要用拜託

**一條違反了也不會報錯的規則，會被違反，而且你不會知道。**

某個專案寫著「代理絕不可碰某個資料源」，這條規則被忽略了一個月——查核時發現五個代理
定義檔全都在違反它。沒有人粗心。**違反時沒有任何東西會失敗**，所以完全沒有回饋。

| 層 | 機制 | 強度 |
|---|---|---|
| 提示 | 在代理檔裡寫「不要寫入正本」 | 最弱，只是建議 |
| 工具集 | frontmatter 的 `disallowedTools` | 拿掉能力 |
| Hook | `PreToolUse` 擋掉指令 | 接住從 Bash 漏出去的 |

三層都要。

## 出處

這裡的每一條都是從一個真實專案抽出來的：一個繁體中文的食材與風味搭配資料庫，數千筆
逐筆標註來源的策展資料，一個人用 Claude Code 做了幾個月，Postgres 正本、有三層存取
控制的唯讀對外檢視、以及一個單向寫進筆記軟體的鏡像。

**領域被拿掉了，事故沒有。** `silent-failure-hunting` 裡的每一條都是那邊真的發生過的
事，連代價一起寫下來。那才是文章裡拿不到的部分——流水線的形狀說穿了很明顯，難的是
它會用哪些方式一邊回報成功一邊出錯。

完整版見 [docs/why.zh-TW.md](docs/why.zh-TW.md)。

## 授權

MIT。拿去用、fork、把你不同意的部分刪掉都可以。

如果它幫你省了一個下午，告訴我是哪一條會很有用——這份清單只能靠回報長大。
