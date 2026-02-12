# Desktop Avatar PoC 調査結果 & 実装計画

## 概要

local-sidekick の通知をデスクトップアバター（Shijima-Qt のような常駐キャラクター）から配信する機能の実現可能性調査と PoC 実装計画。

---

## 1. 調査結果

### 1.1 Shijima-Qt の分析（参考実装）

| 項目             | 内容                                        |
| ---------------- | ------------------------------------------- |
| 技術             | C++/Qt6, WebGL                              |
| アニメーション   | スプライトシート（Shimeji方式）             |
| ウィンドウ       | 透過・常時最前面・クリックスルー            |
| 制御             | HTTP API (`127.0.0.1:32456/shijima/api/v1`) |
| 主要機能         | マスコットの生成/削除/移動/振る舞い変更     |
| ライセンス       | GPL-3.0                                     |
| プラットフォーム | macOS, Linux, Windows                       |

**参考ポイント**: HTTP API で外部からキャラクターを制御できる設計は local-sidekick との連携に適している。ただし GPL-3.0 のためコード流用は不可。ゼロから自作する。

### 1.2 透過ウィンドウ技術の比較

#### アプローチ A: Electron BrowserWindow（推奨）

```typescript
const avatarWindow = new BrowserWindow({
  width: 200,
  height: 300,
  transparent: true, // 背景透過
  frame: false, // フレームなし
  resizable: false, // リサイズ不可（透過時の制約）
  hasShadow: false, // 影なし
  webPreferences: {
    contextIsolation: true,
    preload: join(__dirname, "preload.js"),
  },
});

// 常に最前面（floating レベル = Dock より上）
avatarWindow.setAlwaysOnTop(true, "floating");

// クリックスルー（マウスイベントを下のウィンドウに透過）
// ただし forward: true で mousemove は受け取る（ホバー検出用）
avatarWindow.setIgnoreMouseEvents(true, { forward: true });
```

**利点**:

- 既存の Electron アプリに直接統合可能（BrowserWindow を追加するだけ）
- React/TypeScript でアバター UI を実装可能
- WebSocket/IPC を既存のアーキテクチャと共有
- アニメーションは Web 技術（Canvas, CSS, Lottie, Live2D WebGL）

**制約**:

- 透過ウィンドウはリサイズ不可
- DevTools を開くと透過が壊れる
- macOS でネイティブ影が表示されない
- ウィンドウ全体の不透明度は `setOpacity()` で制御

#### アプローチ B: Swift/AppKit ネイティブ

```swift
let window = NSWindow(
    contentRect: NSRect(x: 0, y: 0, width: 200, height: 300),
    styleMask: .borderless,
    backing: .buffered,
    defer: false
)
window.isOpaque = false
window.backgroundColor = .clear
window.level = .floating
window.ignoresMouseEvents = true
window.collectionBehavior = [.canJoinAllSpaces, .transient]
```

**利点**: パフォーマンス最適、macOS ネイティブの挙動
**欠点**: Electron との IPC が複雑、別プロセス管理が必要、macOS 限定

#### アプローチ C: Tauri

**利点**: 軽量（Electron比1/10のバイナリサイズ）
**欠点**: 既存の Electron アプリとの統合が不可、完全な書き直しが必要

#### 結論

**Electron BrowserWindow アプローチを採用**。既存アーキテクチャとの親和性が最も高く、追加の BrowserWindow を生成するだけで実現可能。

### 1.3 アニメーション技術の比較

| 技術                   | 複雑度 | パフォーマンス | 表現力   | アセット作成              | PoC適性  |
| ---------------------- | ------ | -------------- | -------- | ------------------------- | -------- |
| **CSS/Canvas**         | 低     | 高             | 低〜中   | 簡単                      | **最適** |
| **Lottie (dotLottie)** | 低〜中 | 高             | 中〜高   | After Effects/LottieFiles | 適       |
| **Rive**               | 中     | 高             | 高       | Rive Editor               | 適       |
| **スプライトシート**   | 低     | 高             | 中       | ドット絵/イラスト         | 適       |
| **Live2D**             | 高     | 中             | 非常に高 | Live2D Cubism Editor      | 将来     |
| **Spine**              | 高     | 中             | 高       | Spine Editor($69+)        | 将来     |

#### 各技術の詳細

**CSS/Canvas アニメーション（PoC推奨）**:

- HTML5 Canvas + requestAnimationFrame でスプライトアニメーション
- CSS Animations/Transitions で簡易モーション
- 外部依存なし、即座に実装開始可能
- PoC には十分な表現力

**Lottie / dotLottie（v1推奨）**:

- [lottie-react](https://github.com/LottieFiles/lottie-react) で React 統合
- dotLottie のステートマシン機能で状態遷移を宣言的に定義可能
- LottieFiles マーケットプレイスで無料アセットあり
- `@lottiefiles/dotlottie-react` パッケージ

**Rive（v1〜v2候補）**:

- `@rive-app/react-canvas` で React 統合
- インタラクティブなステートマシンが強力
- Web, iOS, Android 全対応
- 無料プランで十分

**Live2D Cubism SDK for Web（将来）**:

- [CubismWebFramework](https://github.com/Live2D/CubismWebFramework) (TypeScript)
- WebGL レンダリング + Electron = desktop-mascot の実績あり
- 個人/小規模事業者（売上1000万円未満）は SDK 無料
- アセット作成コストが高い（Live2D Cubism Editor $100/年）

#### 結論

**PoC**: CSS/Canvas + スプライトシート（最小工数で動くものを）
**v1**: Lottie または Rive に移行（ステートマシン連動、リッチな表現）
**将来**: Live2D で高品質キャラクターアニメーション

### 1.4 既存オープンソースプロジェクトの調査

| プロジェクト                                                   | 技術スタック                  | 特徴                                         | ライセンス |
| -------------------------------------------------------------- | ----------------------------- | -------------------------------------------- | ---------- |
| [Vixie](https://github.com/Vinceli2401/Vixie)                  | Electron + JS                 | 物理シミュレーション（重力）、スプライト表示 | MIT        |
| [desktop-mascot](https://github.com/temple1026/desktop-mascot) | Live2D + Electron + WebSocket | Python WebSocket でモーション制御            | Live2D SDK |
| [gopheron](https://github.com/kjunichi/gopheron)               | Electron                      | Gopher マスコット                            | -          |
| Shijima-Qt                                                     | C++/Qt6                       | HTTP API、スプライトアニメーション           | GPL-3.0    |

**最も参考になるプロジェクト**: **desktop-mascot**

- Live2D + Electron + **Python WebSocket** でモーション切り替え
- local-sidekick と同じ Python WebSocket パターン
- アーキテクチャを直接参考にできる

### 1.5 macOS 固有の考慮事項

| 項目                           | 必要性                                 | 対応方法                                        |
| ------------------------------ | -------------------------------------- | ----------------------------------------------- |
| アクセシビリティ権限           | 不要（ウィンドウ操作しない場合）       | -                                               |
| 画面収録権限                   | 不要（他ウィンドウをキャプチャしない） | -                                               |
| 透過ウィンドウのパフォーマンス | 中程度の影響                           | アニメーション FPS を 30fps に制限              |
| ウィンドウレベル               | `floating` が適切                      | `setAlwaysOnTop(true, 'floating')`              |
| クリックスルー                 | Electron API で対応                    | `setIgnoreMouseEvents(true, { forward: true })` |
| Spaces/フルスクリーン          | 全 Space に表示                        | `visibleOnAllWorkspaces: true`                  |

**追加の権限は不要**。既存の local-sidekick が必要とする権限（カメラ）のみで動作する。

---

## 2. local-sidekick 統合設計

### 2.1 現在のアーキテクチャ（通知フロー）

```
Engine (Python FastAPI)
  │
  ├── NotificationEngine.evaluate()
  │     → 状態が120秒連続 drowsy/distracted → 通知トリガー
  │     → 90分中80分 focused → over_focus 通知トリガー
  │
  ├── WebSocket broadcast
  │     → {"type": "state_update", "state": "focused", ...}
  │     → {"type": "notification", "notification_type": "drowsy", ...}
  │
  └── REST API
        → GET /api/notifications/pending
        → POST /api/notifications/{id}/respond

Electron Main Process
  │
  ├── startStatePolling() → 5秒間隔でHTTPポーリング
  │     → /api/state → updateTrayIcon()
  │     → /api/notifications/pending → showNotification()
  │
  └── showNotification() → macOS ネイティブ通知
        → onAction → POST /api/notifications/{id}/respond

Renderer (React)
  │
  └── useEngineState() → WebSocket /ws/state
        → state_update → Dashboard/Timeline 更新
        → notification → NotificationCard 表示
```

### 2.2 アバター統合後のアーキテクチャ

**設計思想**: sidekick = 相棒。ユーザーの集中を妨げず、困っている時だけ助ける。

```
Engine (Python FastAPI)    ← 変更なし
  │
  ├── WebSocket /ws/state
  │     → state_update + notification
  │
  └── REST API（既存のまま利用）

Electron Main Process
  │
  ├── mainWindow (既存)     ← 変更なし
  │
  ├── avatarWindow (新規)   ← 透過 BrowserWindow
  │     ├── transparent: true, frame: false
  │     ├── alwaysOnTop: 'floating'
  │     ├── ignoreMouseEvents: true (常時クリックスルー)
  │     ├── show/hide で表示・非表示を切り替え
  │     └── WebSocket → Engine の状態を直接受信
  │
  ├── avatar IPC handlers (新規)
  │     └── 'avatar-toggle' → avatarWindow show/hide
  │
  └── startStatePolling()   ← 条件分岐
        → avatar ON → avatarWindow の表示状態を制御
        → avatar OFF → 従来の macOS 通知
```

### 2.3 アバターステートマシン設計

**基本方針**: 集中時は隠れて邪魔しない。問題検出時だけ登場して助ける。

```
┌──────────────────────────────────────────────────────┐
│                    hidden (非表示)                     │
│          focused のみ                                  │
│          → avatarWindow.hide()                        │
│          ユーザーの集中を邪魔しない                     │
└───────┬──────────────────┬───────────────┬────────────┘
        │ drowsy 検出      │ distracted    │ over_focus
        │ (通知トリガー)   │ (通知トリガー) │ (通知トリガー)
        ▼                  ▼               ▼
┌───────────────┐ ┌────────────────┐ ┌─────────────────┐
│  wake-up      │ │  peek          │ │  stretch        │
│  (起こす！)   │ │  (ひょっこり)  │ │  (休もう！)     │
│               │ │                │ │                 │
│ 画面上を      │ │ 画面端から     │ │ ゆっくり        │
│ 動き回って    │ │ ひょっこり     │ │ 画面に登場して  │
│ ユーザーを    │ │ 顔を出して     │ │ ストレッチ      │
│ 起こす        │ │ 注意を引く     │ │ を促す          │
│               │ │                │ │                 │
│ + 吹き出し    │ │ + 吹き出し     │ │ + 吹き出し      │
└───────┬───────┘ └───────┬────────┘ └────────┬────────┘
        │                 │                   │
        └─────────────────┼───────────────────┘
                          │ 状態回復（focused等に戻る）
                          ▼
                 ┌─────────────────┐
                 │  retreat        │
                 │  (退場)         │
                 │  → フェードアウト│
                 │  → hide()       │
                 └─────────────────┘

┌──────────────────────────────────────────────────────┐
│                   dozing (居眠り)                      │
│          away / idle / Engine未接続                    │
│          座った姿勢でうとうと、ZZZ表示                  │
│          ユーザー不在 or 待機中のかわいい演出            │
└──────────────────────────────────────────────────────┘
```

**状態→アバター動作マッピング**:

| Engine 状態  | 表示       | アバター動作       | アニメーション                               | 吹き出し                           |
| ------------ | ---------- | ------------------ | -------------------------------------------- | ---------------------------------- |
| `focused`    | **非表示** | 隠れる             | - (集中を邪魔しない)                         | なし                               |
| `drowsy`     | **表示**   | 全力で起こす       | 画面上をジャンプ・走り回る、手を振る         | 「眠気が来ています！立ちましょう」 |
| `distracted` | **表示**   | 控えめに注意を引く | 画面端からひょっこり顔を出す                 | 「集中が途切れています」           |
| `away`       | **表示**   | 座って居眠り       | 座った姿勢でうとうと、ZZZ表示                | なし                               |
| `idle`       | **表示**   | 座って居眠り       | 座った姿勢でゆっくり眠くなる                 | なし                               |
| `over_focus` | **表示**   | 休憩を促す         | ゆっくり画面中央に登場、ストレッチモーション | 「休憩しませんか？」               |

### 2.4 吹き出し通知の設計

吹き出しはユーザーへの一方向メッセージ。応答ボタンは不要（アバターの動きで十分伝わる）。

```
┌──────────────────────────┐
│  眠気が来ています！       │
│  立ちましょう             │
└────────────┬─────────────┘
             │ (吹き出しの尻尾)
             ▼
        ┌─────────┐
        │ アバター  │  ← 動き回っている
        │  (>_<)   │
        └─────────┘
```

**実装方針**:

- 常時 `setIgnoreMouseEvents(true)` → 常にクリックスルー（操作を一切邪魔しない）
- 吹き出しは数秒後に自動消去（アバターの動きは状態が変わるまで継続）
- ユーザー応答は不要（状態が `focused` に戻れば自動的にアバター退場）

### 2.5 設定項目（Settings.tsx に追加）

| 設定                    | デフォルト     | 説明                      |
| ----------------------- | -------------- | ------------------------- |
| avatar_enabled          | true           | アバター表示 ON/OFF       |
| avatar_position         | "bottom-right" | 画面上の位置              |
| avatar_size             | "medium"       | small / medium / large    |
| avatar_character        | "default"      | キャラクター選択          |
| use_avatar_notification | true           | アバター経由の通知 ON/OFF |

---

## 3. PoC 実装計画

### 3.1 PoC スコープ

#### やること (Must)

- [ ] Electron で透過 BrowserWindow を生成
- [ ] アバターキャラクターの描画（CSS/Canvas スプライト）
- [ ] Engine WebSocket からの状態受信
- [ ] 状態に応じたアバター表示/非表示の切り替え
- [ ] 状態別アニメーション（drowsy=動き回る、distracted=ひょっこり、over_focus=ストレッチ）
- [ ] 吹き出し通知表示（一方向メッセージ、自動消去）

#### やらないこと (Won't)

- キャラクター選択 UI
- ドラッグ&ドロップでの位置変更
- 物理シミュレーション（重力、ウィンドウ衝突）
- Live2D / Rive 統合
- 複数キャラクター表示
- キャラクターのカスタマイズ

### 3.2 ファイル構成

```
client/
├── electron/
│   ├── main.ts              # avatarWindow 生成を追加
│   ├── avatar-window.ts     # 新規: アバターウィンドウ管理 (show/hide制御)
│   ├── notification.ts      # 条件分岐追加（avatar or OS通知）
│   └── preload-avatar.ts    # 新規: アバター用 preload
│
├── src/
│   ├── avatar/              # 新規: アバター専用ディレクトリ
│   │   ├── AvatarApp.tsx    # アバター React ルート
│   │   ├── AvatarCharacter.tsx  # キャラクター描画 + 動きアニメーション
│   │   ├── SpeechBubble.tsx # 吹き出しコンポーネント（一方向メッセージ）
│   │   ├── useAvatarState.ts    # Engine WebSocket 接続
│   │   ├── avatar-state-machine.ts  # 表示/非表示 + 動作制御
│   │   ├── sprites/         # スプライト画像
│   │   │   ├── wake-up.png  # drowsy時: 動き回るモーション
│   │   │   ├── peek.png     # distracted時: ひょっこり顔出し
│   │   │   ├── stretch.png  # over_focus時: ストレッチ促し
│   │   │   ├── dozing.png   # away/idle時: 座って居眠り
│   │   │   └── retreat.png  # 退場アニメーション
│   │   └── avatar.html      # アバターウィンドウ HTML
│   └── ...
```

### 3.3 実装ステップ（推定 2〜3 日）

#### Step 0: 専用フォルダでPoC ブランチの作成

実装開始前に、専用フォルダ（/Users/s-ohkuma/code/genai/my-agents/local-sidekick）に移動し、必ず PoC 用のブランチを作成する:

```bash
git checkout main
git pull origin main
git checkout -b feat/avatar-poc
```

全ての PoC 作業はこのブランチ上で行い、main には直接コミットしない。

#### Step 1: 透過ウィンドウの基盤（0.5日）

**avatar-window.ts**:

- `BrowserWindow` 生成（transparent, frameless, alwaysOnTop）
- `setIgnoreMouseEvents(true)` を常時設定（常にクリックスルー）
- `show()` / `hide()` による表示切り替え
- avatar.html のロード
- IPC ハンドラー設定

**検証項目**:

- [ ] 透過ウィンドウが正しく表示される
- [ ] デスクトップ上のクリックが透過される
- [ ] 全 Spaces で表示される

#### Step 2: アバターキャラクター描画（0.5日）

**AvatarCharacter.tsx**:

- Canvas ベースのスプライトアニメーション
- 3 動作モード（wake-up / peek / stretch）+ 退場アニメーション
- `requestAnimationFrame` で 30fps アニメーション
- wake-up: 画面上をランダムに移動（ジャンプ、左右走行）
- peek: 画面端からスライドイン
- stretch: 画面中央にフェードイン

**検証項目**:

- [ ] 各動作のアニメーションが正しく再生される
- [ ] 透過背景で正しく描画される
- [ ] 退場（フェードアウト）が滑らかに動作する

#### Step 3: Engine 連携（0.5日）

**useAvatarState.ts**:

- WebSocket `/ws/state` に接続
- `state_update` メッセージでアバター状態切り替え
- `notification` メッセージで吹き出し表示トリガー

**avatar-state-machine.ts**:

- focused → hidden（`avatarWindow.hide()`、集中を邪魔しない）
- away/idle → dozing（座って居眠りアニメーション）
- drowsy/distracted/over_focus → visible + 対応アニメーション
- 状態回復（focused）時 → retreat アニメーション → hidden

**検証項目**:

- [ ] Engine の状態変化がリアルタイムでアバターに反映
- [ ] WebSocket 切断時の再接続

#### Step 4: 吹き出し通知（0.5日）

**SpeechBubble.tsx**:

- 吹き出し UI（一方向メッセージのみ、ボタンなし）
- アバターの上部に表示
- 数秒後に自動消去（吹き出しのみ消え、アバターの動きは継続）
- CSS アニメーションでフェードイン/フェードアウト

**notification.ts 修正**:

- アバターモード時は OS 通知をスキップ
- 代わりに IPC でアバターウィンドウに通知データ送信

**検証項目**:

- [ ] 吹き出しがアバター登場と同時に表示される
- [ ] 数秒後に吹き出しが自動消去される
- [ ] アバターの動きは状態が変わるまで継続する

#### Step 5: 統合テスト & 調整（0.5〜1日）

- Engine 全状態での動作確認
- 通知フロー E2E テスト
- パフォーマンス測定（CPU/メモリ）
- 位置調整、アニメーションの微調整

### 3.4 技術的リスクと対策

| リスク                                             | 影響度 | 対策                                                           |
| -------------------------------------------------- | ------ | -------------------------------------------------------------- |
| 透過ウィンドウの描画不具合（macOS バージョン依存） | 中     | 早期に Step 1 で検証、問題あれば `setOpacity` で代替           |
| Canvas アニメーションのパフォーマンス              | 低     | 30fps 制限、簡素なスプライトで十分                             |
| WebSocket 二重接続（既存 + アバター）              | 低     | Engine 側は複数クライアント対応済み（ConnectionManager）       |
| アバターと他ウィンドウの z-order 競合              | 低     | `floating` レベルで十分、問題なら `screen-saver` に変更        |
| show/hide の頻繁な切り替えによるちらつき           | 中     | フェードイン/フェードアウトで緩和、debounce で状態変化を安定化 |

---

## 4. 将来の拡張ロードマップ

### Phase 1: PoC（今回）

- 基本的なスプライトアニメーション
- 状態連動 + 吹き出し通知

### Phase 2: Lottie / Rive 移行

- dotLottie ステートマシンで宣言的にアニメーション制御
- LottieFiles/Rive マーケットプレイスから高品質アセット導入
- スムーズな状態遷移アニメーション

### Phase 3: Live2D 統合

- Live2D Cubism SDK for Web (TypeScript) 統合
- 表情パラメータと Engine 状態の連動
- 目のトラッキング（カメラデータ流用）
- ユーザーによるモデルカスタマイズ

### Phase 4: インタラクション強化

- ドラッグで位置変更
- デスクトップ上を歩く（Shijima-Qt 風）
- ウィンドウのフチに座る
- AI チャット（Gemini 連携で会話）

---

## 5. 結論

### 実現可能性: **高い**

| 評価項目                     | 結果                                                       |
| ---------------------------- | ---------------------------------------------------------- |
| 技術的実現性                 | **可能**。Electron の既存 API で全て実現可能               |
| 既存アーキテクチャとの親和性 | **非常に高い**。BrowserWindow 追加 + WebSocket 共有のみ    |
| 実装工数（PoC）              | **2〜3 日**（1人で実装可能）                               |
| Engine への変更              | **不要**。既存の WebSocket + REST API をそのまま利用       |
| パフォーマンス影響           | **軽微**。透過ウィンドウ + 30fps Canvas は低負荷           |
| ユーザー体験向上             | **大きい**。OS 通知 → キャラクター通知で親しみやすさが向上 |

### 推奨アプローチ

1. `git checkout -b feat/avatar-poc` で PoC ブランチを作成
2. **Electron BrowserWindow** で透過アバターウィンドウを作成
3. **CSS/Canvas + スプライトシート** で PoC アニメーション
4. **既存 WebSocket** で Engine 状態を受信（変更不要）
5. **sidekick コンセプト**: 集中時は隠れ、困っている時だけ登場して助ける
6. **吹き出し**は一方向メッセージ（ボタンなし、常時クリックスルー）
7. 将来的に **Lottie → Live2D** へアニメーション品質を段階的に向上

---

## 参考リンク

- [Electron BrowserWindow API](https://www.electronjs.org/docs/latest/api/browser-window)
- [Electron Custom Window Styles](https://www.electronjs.org/docs/latest/tutorial/custom-window-styles)
- [Vixie - Electron Desktop Pet](https://github.com/Vinceli2401/Vixie) (MIT)
- [desktop-mascot - Live2D + Electron](https://github.com/temple1026/desktop-mascot)
- [Shijima-Qt](https://github.com/pixelomer/Shijima-Qt) (GPL-3.0, 参考のみ)
- [Live2D Cubism SDK for Web](https://docs.live2d.com/en/cubism-sdk-tutorials/sample-build-web/)
- [Live2D SDK License](https://www.live2d.com/en/sdk/license/) (個人/小規模無料)
- [dotLottie State Machines](https://lottiefiles.com/state-machines)
- [lottie-react](https://github.com/LottieFiles/lottie-react)
- [Rive](https://rive.app/)
- [Electronでデスクトップマスコットを開発](https://hackmd.io/@X2Pp0b6vQralEd1mmBOi7Q/SJ6Y9dbWi)
