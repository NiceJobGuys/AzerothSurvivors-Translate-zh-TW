# Azeroth Survivors 繁體中文化

適用於 **Azeroth Survivors 0.116.0（Windows，Build `7ea12bb5`）**，包含 **2,929 筆主語系文字**及 **43 個原版資源檔的 45,897 個文字欄位**。主語系以原簡中譯文轉換繁體字，資源補譯沿用英文字串一致的 CoA／官方中英對照及人工修訂，並統一常見術語。

遊戲官方網站：https://wow.aethus.pl/

| 適用遊戲版本（Windows） | 遊戲 Build | 中文化版本 | 翻譯筆數 |
| --- | --- | --- | --- |
| **0.116.0** | `7ea12bb5` | [v1.2.0](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/tag/v1.2.0) | 主語系 2,929；資源欄位 45,897 |
| 0.116.0 | `7ea12bb5` | [v1.1.0](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/tag/v1.1.0) | 2,929（僅主語系） |
| 0.102.3 | `f78e6fab` | [v1.0.0](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/tag/v1.0.0) | 2,632 |

遊戲版本與 Build 由各版原始 EXE 的內嵌版本字串確認。中文化版本號與遊戲版本號分開計算；檢查日期為 2026-10-26。

以原版 SHA-256 鎖定相容版本：

```text
d57dbb9f6b325e502204940ac7e3b82bab2ea7db6022c68a9b2bebb91c556bc9
```

中文化工具版本為 **1.2.0**。本次補入原版介面、技能／物品資料及地圖標記；修正回報的 Raven Hill、Contested Territory、效果剩餘時間與角色資訊提示漏譯。資源欄位數含重複引用，並非不重複句子數。遊戲 **0.102.3** 請使用 [v1.0.0](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/tag/v1.0.0)。

## 下載與套用

1. 從[最新版本](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/latest)下載 `AzerothSurvivors-zhTW-1.2.0.zip`，完整解壓並保留 JSON、程式與 `vendor` 目錄。
2. 需要 Windows、Python 3.10 以上及本機的微軟正黑體。安裝工具需要的字型處理套件：

```powershell
python -m pip install -r .\requirements.txt
```

3. 正常關閉遊戲，在解壓後的目錄執行下列指令；遊戲與備份路徑可依實際位置調整：

```powershell
python -B -X utf8 .\patch.py apply "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe" "D:\Code\Lab Testing\Artifacts\backup\azerothsurvivors-zh-tw-1.1.0"
python -B -X utf8 .\asset_patch.py apply "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors" "D:\Code\Lab Testing\Artifacts\backup\azerothsurvivors-zh-tw-1.1.0"
```

工具驗證整個原版 EXE 的雜湊，保留原檔備份後，才替換遊戲 EXE。文字與中文字型沿用原有固定容量，不移動執行檔其他資料；超出容量會停止。工具會從玩家本機的 `C:\Windows\Fonts\msjh.ttc` 產生字型子集，不下載、不安裝或發布字型。

第二條指令核對原版資源雜湊，在本機產生 `Data/patch-Z.MPQ` 中文覆蓋包，不覆寫原版 MPQ。已套用 v1.1.0 者沿用原備份目錄；第一條會確認已套用，第二條補上資源中文化。若同名覆蓋包不是本工具建立，工具會停止而不覆蓋。

4. 重新啟動遊戲，在語言選單選擇「繁體中文」。主語系補丁佔用簡中位置；其他主語系選項保留，但資源覆蓋包啟用時，原版介面與資料文字固定使用繁中。

若只要產生另一份 EXE 供檢查，不修改來源：

```powershell
python -B -X utf8 .\patch.py build "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe" ".\AzerothSurvivors-zhTW.exe"
```

輸出檔必須不存在。此 build 指令只產生主語系 EXE；資源覆蓋包由上述 asset_patch.py apply 產生。EXE 需搭配遊戲原有 Data 資料夾才能執行。

## 還原與更新

備份目錄內的 `AzerothSurvivors.exe.original` 是玩家自己的原檔；`installed.json` 記錄原版、補丁及譯文雜湊。請保留兩者，不要把備份分享給其他人。

`assets-installed.json` 記錄資源覆蓋包的雜湊及修改欄位。更新同一遊戲版本的資源翻譯時，保留此收據並沿用備份目錄。

正常關閉遊戲後還原：

```powershell
python -B -X utf8 .\asset_patch.py restore "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors" "D:\Code\Lab Testing\Artifacts\backup\azerothsurvivors-zh-tw-1.1.0"
python -B -X utf8 .\patch.py restore "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe" "D:\Code\Lab Testing\Artifacts\backup\azerothsurvivors-zh-tw-1.1.0"
```

先核對並移除本工具的中文資源覆蓋包，再還原 EXE。還原會核對目前遊戲與收據，以及原版備份的完整性；不覆蓋已更新或另行修改的檔案。只想停用資源中文化時，僅執行第一條。主語系譯文修改後須先還原 EXE，再重新套用；資源譯文可使用原收據直接更新。

遊戲更新可能覆蓋補丁。新版 EXE 雜湊不同時，本工具會停止，須重新檢查語系、字型位置及新增文字後才能適配。不同遊戲版本使用不同備份目錄；本次保留 1.0.0 備份，另建立 1.1.0 備份。不要用舊版備份覆蓋新版遊戲。

若替換時因遊戲未關閉、權限或儲存空間不足而失敗，原版備份會保留；同目錄可能留下 `AzerothSurvivors.exe.zhtw-new`。請先查看錯誤與雜湊，不要把它當成已安裝成功。

## 原始碼與翻譯

- `patch.py`：版本校驗、字型子集、等長補丁、套用及還原。
- `asset_patch.py`：原版資源的校驗、文字替換、MPQ 建置、字型、套用及還原。
- `assets-zh-TW.json`：資源英文／繁中對照及來源雜湊；依此檔即可在玩家自己的遊戲資料上重建覆蓋包。
- `assets-overrides.json`：人工用語、屬性及介面修訂的維護紀錄。
- `tools/export_assets.py`：維護者由本機盤點 SQLite 匯出資源對照；一般套用及重建不需要該資料庫或 CoA 工作區。
- `vendor/mpq/`：wc3-mcp 1.17.0 的 MPQ 模組，保留原 MIT 授權與來源說明。
- `en.json`、`zh-CN.json`：從相容版本擷取的語系文字。
- `zh-TW.json`：完整繁中譯文，亦為套用工具使用的字典。
- `wow-terms.json`：沿用 CoA 術語表的 376 個既有名稱；不包含其草稿及語境不明的通用詞。
- `glossary.json`：繁體轉換後的用語替換，單次匹配，避免「食人魔→巨魔→食人妖」的連鎖誤換。
- `overrides.json`：逐鍵人工修訂；優先於術語表。
- `baseline.json`：相容 EXE 雜湊、資料區塊位置與大小。
- `tools/prepare.py`：從玩家自己的原版擷取語系，並重建繁中譯文。
- `tests/test_patch.py`：參數、容量、修改範圍、版本拒絕、套用及還原的測試。
- `tests/test_assets.py`：資源文字、數值、封包與套用還原測試，以及截圖回報漏譯的回歸測試。
- `requirements.txt`：套用工具需要的 fontTools 版本。

重建譯文另需 `opencc-python-reimplemented==0.1.7`。使用 `s2t` 字體轉換搭配明列術語，不使用會誤轉「減免提高」的 `s2twp` 自動用語轉換。

```powershell
python -m pip install opencc-python-reimplemented==0.1.7
python -B -X utf8 .\tools\prepare.py "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe"
python -B -X utf8 -m unittest discover -s .\tests -v
```

修改翻譯時，將逐鍵修正記入 `overrides.json` 再重建，避免下次重建覆蓋修改。`{name}`、`{n}`、`%s` 等參數的名稱與出現次數必須保留。遊戲原有數值也必須保留。

資源譯文以 `assets-zh-TW.json` 為建置來源；修改其 target／對照值並同步人工修訂紀錄後，重新執行 asset_patch.py apply。Lua 指令別名、刪除確認代碼與非顯示用 API 值不得當成一般文字翻譯。

## 驗證與已知限制

- 全部 2,929 筆的鍵、非空文字與格式參數已檢查；數字未變更。
- 25 項測試通過，包含地圖標記與區域名稱一致、角色提示及秒／分／時／天倒數的回歸測試。
- 建置後回讀語系 JSON，並驗證三個指定區塊之外的 EXE 資料一致。
- 字型保留原有中文字型的全部字元，另加入繁中譯文所需字元；漢字缺字檢查通過。
- 遊戲既有的表情符號繼續使用原本的 fallback，未新增表情符號字型。
- 資源覆蓋包逐檔回讀一致；DBC 僅變更文字參照與新增字串，非文字欄位保持一致。新增字型涵蓋補譯漢字。
- 使用者回傳畫面顯示區域、增益效果及角色標籤已使用中文。本次四類漏譯已修正並回讀實際安裝包確認；修正後畫面仍待使用者驗收，未宣稱完整排版測試通過。
- 未處理的舊 WoW 資料、第三方插件、圖片文字及部分硬編碼文字仍可能保留英文；不宣稱全遊戲 100% 中文化。
- 本機已完成備份及套用，EXE 與資源覆蓋包的雜湊均已核對；詳細結果見 `VALIDATION.md`。

Repo 與下載包不包含遊戲 EXE、MPQ、原始字型、玩家存檔或原檔備份。遊戲及原有內容權利屬原權利人，本專案為非官方中文化。
