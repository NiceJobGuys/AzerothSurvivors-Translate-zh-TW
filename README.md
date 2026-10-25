# Azeroth Survivors 繁體中文化

適用於 2026-10-26 更新的 Windows 版，涵蓋遊戲語系表全部 **2,929 筆文字**。以原有簡中譯文轉換繁體字，搭配 CoA 既有繁中術語與人工修訂，替換簡中語系為「繁體中文」；其他語系保留。

遊戲官方網站：https://wow.aethus.pl/

以原版 SHA-256 鎖定相容版本：

```text
d57dbb9f6b325e502204940ac7e3b82bab2ea7db6022c68a9b2bebb91c556bc9
```

中文化工具版本為 **1.1.0**。本次新增 309 筆、移除 12 個舊鍵，另更新既有文字；包含合作連線、外觀及首領提示。原始碼與翻譯公開提供，工具下載包放在 GitHub Releases。前一個遊戲版本請使用 [v1.0.0](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/tag/v1.0.0)。

## 下載與套用

1. 從[最新版本](https://github.com/NiceJobGuys/AzerothSurvivors-Translate-zh-TW/releases/latest)下載 `AzerothSurvivors-zhTW-1.1.0.zip`，完整解壓並保留所有 JSON 與程式。
2. 需要 Windows、Python 3.10 以上及本機的微軟正黑體。安裝工具需要的字型處理套件：

```powershell
python -m pip install -r .\requirements.txt
```

3. 正常關閉遊戲，在解壓後的目錄執行下列指令；遊戲與備份路徑可依實際位置調整：

```powershell
python -B -X utf8 .\patch.py apply "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe" "D:\Code\Lab Testing\Artifacts\backup\azerothsurvivors-zh-tw-1.1.0"
```

工具驗證整個原版 EXE 的雜湊，保留原檔備份後，才替換遊戲 EXE。文字與中文字型沿用原有固定容量，不移動執行檔其他資料；超出容量會停止。工具會從玩家本機的 `C:\Windows\Fonts\msjh.ttc` 產生字型子集，不下載、不安裝或發布字型。

4. 自行啟動遊戲，在語言選單選擇「繁體中文」。原本使用簡中的設定會直接顯示繁中。這份補丁佔用簡中語系位置，不能同時保留簡中選項。

若只要產生另一份 EXE 供檢查，不修改來源：

```powershell
python -B -X utf8 .\patch.py build "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe" ".\AzerothSurvivors-zhTW.exe"
```

輸出檔必須不存在。產生的 EXE 需搭配遊戲原有 Data 資料夾才能執行，不是獨立遊戲安裝包。

## 還原與更新

備份目錄內的 `AzerothSurvivors.exe.original` 是玩家自己的原檔；`installed.json` 記錄原版、補丁及譯文雜湊。請保留兩者，不要把備份分享給其他人。

正常關閉遊戲後還原：

```powershell
python -B -X utf8 .\patch.py restore "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe" "D:\Code\Lab Testing\Artifacts\backup\azerothsurvivors-zh-tw-1.1.0"
```

還原會核對目前遊戲與收據，以及原版備份的完整性；不覆蓋已更新或另行修改的遊戲。重複套用相同譯文或重複還原會直接回報現況。譯文修改後須先還原，再重新套用。

遊戲更新可能覆蓋補丁。新版 EXE 雜湊不同時，本工具會停止，須重新檢查語系、字型位置及新增文字後才能適配。不同遊戲版本使用不同備份目錄；本次保留 1.0.0 備份，另建立 1.1.0 備份。不要用舊版備份覆蓋新版遊戲。

若替換時因遊戲未關閉、權限或儲存空間不足而失敗，原版備份會保留；同目錄可能留下 `AzerothSurvivors.exe.zhtw-new`。請先查看錯誤與雜湊，不要把它當成已安裝成功。

## 原始碼與翻譯

- `patch.py`：版本校驗、字型子集、等長補丁、套用及還原。
- `en.json`、`zh-CN.json`：從相容版本擷取的語系文字。
- `zh-TW.json`：完整繁中譯文，亦為套用工具使用的字典。
- `wow-terms.json`：沿用 CoA 術語表的 376 個既有名稱；不包含其草稿及語境不明的通用詞。
- `glossary.json`：繁體轉換後的用語替換，單次匹配，避免「食人魔→巨魔→食人妖」的連鎖誤換。
- `overrides.json`：逐鍵人工修訂；優先於術語表。
- `baseline.json`：相容 EXE 雜湊、資料區塊位置與大小。
- `tools/prepare.py`：從玩家自己的原版擷取語系，並重建繁中譯文。
- `tests/test_patch.py`：參數、容量、修改範圍、版本拒絕、套用及還原的測試。
- `requirements.txt`：套用工具需要的 fontTools 版本。

重建譯文另需 `opencc-python-reimplemented==0.1.7`。使用 `s2t` 字體轉換搭配明列術語，不使用會誤轉「減免提高」的 `s2twp` 自動用語轉換。

```powershell
python -m pip install opencc-python-reimplemented==0.1.7
python -B -X utf8 .\tools\prepare.py "D:\Games\azeroth-survivors\AzerothSurvivorsWindowsNew\AzerothSurvivors\AzerothSurvivors.exe"
python -B -X utf8 -m unittest discover -s .\tests -v
```

修改翻譯時，將逐鍵修正記入 `overrides.json` 再重建，避免下次重建覆蓋修改。`{name}`、`{n}`、`%s` 等參數的名稱與出現次數必須保留。遊戲原有數值也必須保留。

## 驗證與已知限制

- 全部 2,929 筆的鍵、非空文字與格式參數已檢查；數字未變更。
- 13 項測試通過；已加入 CRLF 語系擷取及字型位於語系之前的回歸測試。
- 建置後回讀語系 JSON，並驗證三個指定區塊之外的 EXE 資料一致。
- 字型保留原有中文字型的全部字元，另加入繁中譯文所需字元；漢字缺字檢查通過。
- 遊戲既有的表情符號繼續使用原本的 fallback，未新增表情符號字型。
- 中文字型改用本機微軟正黑體，字重與字寬會不同；未進遊戲驗證排版、換行及顯示。
- 範圍為遊戲自身語系表；原始 WoW 素材資料、第三方插件、圖片上的文字及未走語系表的硬編碼文字不在本次覆蓋範圍。
- 尚未啟動遊戲實測，也未檢查所有畫面是否使用這份語系表。
- 本機已實際完成備份及套用，安裝後 EXE 與建置版雜湊一致；詳細結果見 `VALIDATION.md`。

Repo 與下載包不包含遊戲 EXE、MPQ、原始字型、玩家存檔或原檔備份。遊戲及原有內容權利屬原權利人，本專案為非官方中文化。
