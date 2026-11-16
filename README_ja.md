# card-gcalc

[English](README.md) · **[取扱説明書](doc_ja/README.md)**

M5Stack [Cardputer-Adv](https://docs.m5stack.com/ja/core/Cardputer-Adv) を、MicroPython ベースのグラフ電卓にするファームウェアです。

- 起動するとアイコンメニューが表示され、13 個のアプリを選べます
- 電卓アプリの計算は 10 進 15 桁 (BCD 相当) で行います。`0.1+0.2-0.3` は 0、`sin(π)` は 0 になります
- Python スクリプトの float は倍精度 (double) です。MicroPython の esp32 ポートは標準では単精度です
- Python プログラムを作成・編集・実行できます (エディタ、REPL、グラフィックス API、numpy 互換の ulab 付き)
- microSD カードの読み書きと、GPIO (Grove・拡張ヘッダ) の入出力に対応しています
- プラグインで、ファームウェアを書き直さずにアプリを追加できます (サンプルとして BASIC インタプリタを同梱)
- 表示言語を英語と日本語で切り替えられます (Settings → Language / 言語)

## アプリ

| # | アプリ | 日本語表示 | 内容 |
|---|---|---|---|
| 1 | **Calc** | 計算 | 計算履歴付きの計算画面。変数 (`→A` / `A=…`)、Ans、厳密表示の切り替え (分数・π・√)、Deg/Rad/Gra、Norm/Fix/Sci/Eng、複素数 |
| 2 | **Graph** | グラフ | Y1〜Y6 (y=f(x)・極座標 r=f(θ)・媒介変数)。パン・ズーム・トレース。Analysis (根、極小・極大、交点、y(x)、x(y)、dy/dx、∫dx の塗りつぶし) |
| 3 | **3D Graph** | 3Dグラフ | Z1〜Z3 (z=f(x,y)、パラメーター、テンプレート (直線・平面・球・円柱・円錐)、X 軸・Y 軸回転体)。回転・ズーム・軸方向表示・自動回転・トレース。Analysis (断面、交点・交線、位置関係) |
| 4 | **Table** | 数表 | 関数の数表。開始値と刻み幅を変更でき、際限なくスクロールできる |
| 5 | **Equation** | 方程式 | 2〜4 次多項式 (複素数解と厳密形)、2〜4 元連立 1 次方程式、ソルバ (f(x)=g(x) の範囲内の全解) |
| 6 | **Stats** | 統計 | リスト L1〜L3、1 変数・2 変数統計、回帰 (1 次、2 次、指数、対数、累乗)、散布図・ヒストグラム・箱ひげ図、確率分布 (正規、二項、ポアソン) |
| 7 | **Matrix** | 行列 | 行列 A〜F (最大 6×6)。det・逆行列・転置・ランク・RREF・加減乗・累乗・Ax=b |
| 8 | **Base Conv** | 進数計算 | DEC/HEX/OCT/BIN、8/16/32/64bit、符号の有無、AND/OR/XOR/NOT/NAND/NOR/XNOR/SHL/SHR/MOD |
| 9 | **Python** | Python | スクリプトの一覧 (/programs と /sd/programs)、エディタ、実行 |
| 10 | **Shell** | シェル | Python REPL (履歴、複数行ブロック) |
| 11 | **Files** | ファイル | フラッシュ・SD のファイル操作 (閲覧、コピー・移動、削除、名前変更、mkdir、SD のマウント・アンマウント) |
| 12 | **GPIO** | GPIO | G1/G2 (Grove) と G3/G4/G5/G6/G13/G15 (EXT) の IN / OUT / ADC / PWM、I2C スキャン |
| 13 | **Settings** | 設定 | 角度単位、表示形式、複素数、輝度、SD 自動マウント、プラグインの管理、メモリ情報、初期化 |

インストールしたプラグインは、Settings の後ろに並びます。

## 3D グラフ

3 つまでのグラフ (Z1〜Z3) を同時に描きます。

- 種類 (一覧で F2):
  - Z= : `z=f(x,y)` を x・y で入力します
  - パラメーター: X(s,t)、Y(s,t)、Z(s,t) を s・t で入力します。範囲は表示範囲の S・T で決めます
  - 直線: 点とベクトル、または 2 点
  - 平面: aX+bY+cZ=d、点と 2 ベクトル、または 3 点
  - 球: 中心と半径、または X²+Y²+Z²+aX+bY+cZ+d=0
  - 円柱・円錐: 半径、高さ (Z の範囲)、中心 (軸は Z 軸に平行)
  - X 軸回転体・Y 軸回転体: `y=f(x)` を x の範囲 (Xmin〜Xmax) で回転させた立体
- 一覧: Enter で式・値を編集、F1 描画の有無、F3 色、F4 表示範囲 (Xmin〜Zmax、grid、S・T、角度 θ・φ、ラベル・軸・外枠・メッシュ線の表示)、F5 削除、F6 描画
- グラフ画面:
  - 矢印キー (`;` `.` `,` `/`) で上下左右に回転し、`+` / `-` で拡大・縮小します
  - F1 トレース: 矢印でメッシュ上の点を動かし、X・Y・Z の値を表示します (10 進で正確に計算)。F2 / F3 で対象のグラフを切り替え、Enter で座標を入力します
  - F2 ズーム: 拡大、縮小、X・Y・Z 軸方向から見る、元の表示
  - F4 解析:
    - 断面: X=c・Y=c・Z=c の平面で切った切り口を描きます (F1 / F2 で平面を移動、Enter で値を入力)
    - 交点・交線: 直線・平面・球の組み合わせについて、交点の座標、交線の式、交わりの円の中心と半径を求めます
    - 位置関係: 2 直線・2 平面・直線と平面が、交わる・垂直・平行・ねじれの位置・同一のどれかを判定します
  - F5 自動回転: 左右または上下に 2 周回転します (キーを押すと止まります)
- 面は向きに応じた陰影を付けて塗り、表示範囲の箱で切り取ります。メッシュの細かさは grid (2〜50) で変えられます

## 計算の精度 (10 進演算)

電卓アプリ (計算、グラフ、3D グラフ、数表、方程式、統計、行列) の数値は、関数電卓と同じ 10 進の浮動小数点数です。

- 仮数は 10 進 15 桁、指数は ±99 です。演算のたびに 15 桁へ四捨五入します。表示は通常 10 桁です。
  - 範囲を超えるとエラー (Math error) になり、1E-99 より小さい値は 0 になります
- 10 進で正確に書ける数は誤差なく扱えます。`0.1+0.2-0.3` は 0、`1-0.9` は 0.1 です
- 関数 (√、ln、sin など) は 18 桁で計算してから 15 桁に丸めます。ずれても 15 桁目の 1 単位以内です
- 三角関数:
  - 度・グラードでは周期を 10 進のまま正確に処理するので、`sin(180)` や `cos(90)` は 0 です
  - ラジアンでは、π の倍数として入力した値 (`sin(π)`、`cos(π/2)`、`tan(2π)` など) を正確な倍数として扱います
- 複素数も、実部・虚部とも 10 進です。`e^(iπ)` は -1、`i^2` は -1 になります
- ガンマ関数・誤差関数 (統計の正規分布など) だけは、内部で倍精度の float を使い、結果を 15 桁に丸めています
- Python スクリプト (Python、Shell) の数値は従来どおり float です。電卓の 10 進数は、C モジュール `bcd` (`firmware/cmodules/bcd`) で実装しています
  - 仮数は 4 ビットずつの BCD ではなく 2 進整数で保持しますが、10 進で計算・丸めるので結果は BCD と同じです

## キー操作

### 共通

| キー | 動作 |
|---|---|
| `fn` + `;` `.` `,` `/` | ↑ ↓ ← → (テキストを入力しない画面では `;` `.` `,` `/` だけでも矢印になる) |
| `fn` + `` ` `` | ESC / 戻る |
| `fn` + `1`〜`6` | F1〜F6 (画面下のソフトキー) |
| `fn` + `BS` | 前方削除 (DEL) |
| `fn` + `-` / `=` | 行頭 / 行末 |
| `fn` + `[` / `]` | ページアップ / ダウン |
| `fn` + `h` | キーマップのヘルプ |

修飾キー (`shift` `ctrl` `opt` `alt` `fn`) は、単独で押して離すと次の 1 キーだけ有効になります (ラッチ)。もう一度押すとロックされ、さらに押すと解除されます。状態はステータスバーに表示されます。

### 数式入力 (`opt` / `alt`)

| キー | `opt` | `alt` |
|---|---|---|
| s / c / t | sin( cos( tan( | sin⁻¹( cos⁻¹( tan⁻¹( |
| l / g / e | ln( log( e^( | log2( log( exp( |
| q / r / w | √( ∛( root( | sqrt( round( fpart( |
| u | 10^( | rad( |
| h / j / k | θ ∫( k | sinh( cosh( tanh( |
| p / a / x / y / i | π Ans x y i | isprime( atan2( max( — int( |
| f / n / m / b | ! nCr( mod( abs( | floor( nPr( min( gcd( |
| d / z / o / v | d/dx( Σ( ∏( solve( | deg( randint( rand() lcm( |
| 1 / 2 / 3 / 6 / 0 | ⁻¹ ² ³ ^ E(×10ⁿ) | fact( ³ ∛( |
| = / 8 / / / 5 / 9 / . | → × ÷ % ( , | — ∞ |

式の書き方の例: `2sin(π/6)`、`x²-3x+2`、`3→A`、`A(A+1)`、`∫(x²,0,3)`、`d/dx(x³,2)`、`Σ(k²,k,1,10)`、`solve(x²-2,1)`、`(-8)^(1/3)` (= -2)、`e^(iπ)` (複素数モードで -1)。
暗黙の乗算 (`2x`、`3(x+1)`、`(a)(b)`) に対応しています。閉じ括弧は省略できます。

## Python

スクリプトは `/programs/*.py` に保存されます。Python アプリを初めて開いたとき、`/programs` に .py ファイルが無ければ、サンプル (hello, primes, plot, turtle_star, blink, chart, ulab_demo) が作られます。

- エディタ: `ctrl+s` 保存、`ctrl+r` 実行、`ctrl+f` 検索、`ctrl+g` 行ジャンプ、`ctrl+k` 行カット、`ctrl+u` 貼り付け、`ctrl+z` 元に戻す、`ctrl+d` 行複製、Tab / Shift+Tab でインデント
- 実行中は ESC (`fn`+`` ` ``) または Ctrl+C で中断できます。`while True: pass` のようなループも止まります
- `print` / `input()` は画面のコンソールにつながります

スクリプトから使えるモジュール:

- `cardgcalc`: 画面・キーボード・GPIO などを扱う本機用の API (次節)
- `turtle`: forward、left、circle、color、penup など
- `matplotlib.pyplot`: plot、scatter、bar、hist、axis、grid、text、show
  - データにはリスト・タプルのほか、ulab の ndarray をそのまま渡せます
  - `plot(x, Y)` の Y が 2 次元配列なら、列ごとに別の線として描きます
- `ulab`: numpy / scipy 互換の配列計算モジュール ([ulab](https://github.com/v923z/micropython-ulab) 6.12.1、倍精度、2 次元まで)
  - `from ulab import numpy as np`、`from ulab import scipy`
  - 配列の生成 (`array`、`linspace`、`arange`、`zeros` …)、要素ごとの演算・数学関数、統計 (`mean`、`std`、`max` …)、`linalg` (`inv`、`det`、`dot` …)、`fft`、`polyfit` / `polyval`、`scipy.optimize` / `integrate` など

```python
from ulab import numpy as np
import matplotlib.pyplot as plt
x = np.linspace(0, 4 * np.pi, 200)
plt.plot(x, np.sin(x) * np.exp(-x / 6))
plt.grid(True)
plt.show()
```
- `machine` など、MicroPython 標準のモジュールもそのまま使えます

### cardgcalc モジュール

```python
import cardgcalc
cardgcalc.cls(); cardgcalc.line(0, 0, 239, 134, cardgcalc.RED); cardgcalc.text("hi", 10, 10, cardgcalc.YELLOW, font="large"); cardgcalc.show()
k = cardgcalc.wait_key()            # "a", "ENTER", "UP" ...
cardgcalc.plot(lambda x: x*x, -3, 3)
cardgcalc.pin_out(cardgcalc.G1, 1); v = cardgcalc.analog(cardgcalc.G2); cardgcalc.pwm(cardgcalc.G1, 1000, 50); i2c = cardgcalc.i2c_grove()
```

#### 画面

画面は 240×135 ドットで、原点 (0, 0) は左上です。描画は画面のバッファに対して行われ、スクリプトの実行中は自動で表示に反映されます。すぐに表示したいときは `show()` を呼んでください。

| API | 内容 |
|---|---|
| `W` / `width`、`H` / `height` | 画面の幅 (240) と高さ (135) |
| `cls(c=BLACK)` / `clear(c=BLACK)` | 画面全体を色 c で塗りつぶす |
| `pixel(x, y)` / `pixel(x, y, c)` | 点の色を返す (内部の色値) / 点を描く |
| `set_pixel(x, y, c)` | 点を描く |
| `get_pixel(x, y)` | 点の色を `(r, g, b)` のタプルで返す |
| `line(x0, y0, x1, y1, c=WHITE)` | 直線 |
| `hline(x, y, w, c=WHITE)`、`vline(x, y, h, c=WHITE)` | 水平線、垂直線 |
| `rect(x, y, w, h, c=WHITE)`、`fill_rect(x, y, w, h, c=WHITE)` | 長方形の枠、塗りつぶした長方形 |
| `circle(x, y, r, c=WHITE, fill=False)` | 円 (中心 x, y、半径 r) |
| `ellipse(x, y, rx, ry, c=WHITE, fill=False)` | 楕円 |
| `poly(points, c=WHITE, fill=False)` | 多角形。points は `[(x, y), ...]` |
| `text(s, x, y, c=WHITE, bg=None, font="normal")` | 文字列を描き、描き終えた位置の x 座標を返す。bg=None なら背景は透明。日本語も表示できる |
| `text_width(s, font="normal")` | 文字列の幅 (ドット) |
| `draw_string(s, x, y, c=(0,0,0), bg=(255,255,255))` | 文字列を "medium" フォントで、背景付きで描く |
| `show()`、`wait_vblank()` | 描いた内容をすぐ画面に反映する |
| `brightness(pct)` | バックライトの明るさ (0〜100 %) |

- フォント (`font=`): `"small"` 5×8、`"normal"` 6×10、`"medium"` 6×13、`"large"` 10×20。日本語はどのフォントでも 8×12 で表示されます。
- 色の指定: 色を受け取る引数には、次のどれでも渡せます。
  - `color(r, g, b)` (各 0〜255) が返す値
  - `(r, g, b)` のタプル
  - 色名の文字列: `"black"` `"white"` `"red"` `"green"` `"blue"` `"yellow"` `"cyan"` `"magenta"` `"orange"` `"gray"` `"grey"` `"purple"` `"brown"` `"pink"`
  - 色の定数: `BLACK` `WHITE` `RED` `GREEN` `BLUE` `YELLOW` `CYAN` `MAGENTA` `ORANGE` `GRAY` `GREY`
- `color()` は `color((r, g, b))` や `color("red")` のように、タプルや色名も受け付けます。

#### キーボード

| API | 内容 |
|---|---|
| `get_key()` | 押されたキーを文字列で返す。何も押されていなければ `None` (待たない) |
| `wait_key()` | キーが押されるまで待ち、そのキーを文字列で返す |
| `key_down(name)` / `keydown(name)` | そのキーが今押されていれば `True` (ゲームなどの同時押し判定用) |
| `keys_down()` | 今押されているキーの集合 |

- `get_key()` / `wait_key()` が返す文字列:
  - 文字キーは入力される文字そのもの (`"a"`、`"A"`、`"1"`、`"!"`、`" "` など)
  - `"ENTER"` `"BS"` `"TAB"`
  - fn との組み合わせ: `"UP"` `"DOWN"` `"LEFT"` `"RIGHT"` `"ESC"` `"DEL"` `"F1"`〜`"F10"` `"HOME"` `"END"` `"PGUP"` `"PGDN"`
- `key_down()` に渡すキーの名前:
  - キートップの文字 (小文字、シフト前の文字): `"a"`、`"1"`、`";"` など
  - `"ENTER"` `"BS"` `"TAB"` `"SPACE"` `"ESC"` (`` ` `` キー)
  - `"UP"` `"DOWN"` `"LEFT"` `"RIGHT"`: それぞれ `;` `.` `,` `/` キー
  - 修飾キー: `"SHIFT"` `"FN"` `"CTRL"` `"OPT"` `"ALT"`
- キーの名前の定数 `KEY_*` もあり、`key_down(KEY_OK)` のように使えます。例: `KEY_UP` `KEY_DOWN` `KEY_LEFT` `KEY_RIGHT` (矢印)、`KEY_OK` / `KEY_EXE` (Enter)、`KEY_BACK` (`` ` ``)、`KEY_BACKSPACE`、`KEY_SHIFT`、`KEY_ALPHA` (alt)、`KEY_ZERO`〜`KEY_NINE`、`KEY_PLUS`、`KEY_MINUS`
- 実行中に ESC (`fn`+`` ` ``) または Ctrl+C を押すと、スクリプトは中断されます。

#### 時間・電源

| API | 内容 |
|---|---|
| `sleep(s)`、`sleep_ms(ms)` | 待つ (待っている間も中断キーと画面更新が効く) |
| `ticks_ms()` | ミリ秒単位のカウンタ |
| `battery()` | バッテリー残量 (%) |

#### グラフ

| API | 内容 |
|---|---|
| `plot(f, xmin=-10, xmax=10, ymin=None, ymax=None, c=None, wait=True)` | y=f(x) のグラフを画面全体に描く。ymin / ymax を省略すると自動で縦の範囲を決める。wait=True ならキーが押されるまで待つ |

#### GPIO

| API | 内容 |
|---|---|
| `G1` `G2` (Grove)、`G3` `G4` `G5` `G6` `G13` `G15` (EXT ヘッダ)、`PINS` | ピン番号の定数と、その一覧 |
| `pin_out(p, v=None)` | p を出力にし、v (0 / 1) を出力する。`machine.Pin` を返す |
| `pin_in(p, pull=None)` | p を入力にして値 (0 / 1) を返す。pull は `None` `"up"` `"down"` |
| `analog(p)` | p の電圧 (V、0〜約 3.1) |
| `pwm(p, freq=1000, duty=50)` | PWM 出力 (周波数 Hz、デューティ %)。`duty=None` で停止 |
| `tone(p, freq, ms)` | p に圧電ブザーなどをつないで、音を ms ミリ秒鳴らす |
| `i2c_grove(freq=100000)` | Grove ポート (SDA=G2、SCL=G1) の I2C (`machine.SoftI2C`) |

## プラグイン

ファームウェアを書き直さずに、アプリを追加できます。プラグインは、フラッシュの `/plugins/<名前>/` か SD カードの `/sd/plugins/<名前>/` に置くフォルダです。ホーム画面には、組み込みアプリの後ろに並びます。

```
/plugins/basic/
  plugin.json        マニフェスト
  basic.mpy          入口のモジュール (run() でアプリを開始する)
  baslang.mpy        ほかのモジュールやデータも置ける
  examples/...
```

`plugin.json` の例:

```json
{
  "api": 1,
  "name": "BASIC",
  "name_ja": "BASIC",
  "version": "1.0",
  "module": "basic",
  "glyph": "BAS",
  "color": [200, 90, 40],
  "files": [".bas"],
  "description": "Structured BASIC interpreter"
}
```

| キー | 内容 |
|---|---|
| `api` | 対象とするプラグイン API の版。ファームウェアの版 (`cardgcalc.plugins.API`、現在 1) より新しいと読み込まない |
| `name` / `name_ja` | ホーム画面の名前 (日本語表示のときは `name_ja`) |
| `module` | 入口のモジュール名。省略するとフォルダ名 |
| `icon` / `glyph` | アイコン。`icon` は組み込みアイコンの名前 (`calc`、`graph` など)。`glyph` はタイルに描く 1〜4 文字 |
| `color` | タイルの色 `[r, g, b]` |
| `files` | 担当する拡張子。ファイルアプリの「開くアプリ」から、入口モジュールの `open_file(path)` が呼ばれる |
| `description` / `description_ja` | Settings → Plugins の情報画面に出す説明 |

入口のモジュールの書き方:

- `run()` を定義します。アプリが終わったら return します。
- 実行中は、プラグインのフォルダが `sys.path` の先頭に入ります。同じフォルダのモジュールはそのまま import できます。
- `cardgcalc.plugins.current` で、自分のマニフェスト (`dir` にフォルダのパス) を参照できます。
- 終了すると、プラグインのフォルダから読み込んだモジュールは解放されます。
- 例外は画面に表示されます。
- 本体のモジュールをそのまま使えます。
  - `cardgcalc.hal`: キーボード・LCD
  - `cardgcalc.gfx`、`cardgcalc.ui`: メニュー・入力欄・メッセージ
  - `cardgcalc.console`: スクロールするテキスト画面
  - `cardgcalc.editor`: エディタ
  - `cardgcalc.runner`: 中断キーと描画の自動更新
  - `cardgcalc.storage`、`cardgcalc` (スクリプト用 API)
- `cardgcalc.plugins.translator({"English": "日本語", ...})` で、そのプラグイン専用の翻訳関数 `T()` を作れます。
- エディタは、`cardgcalc.editor.edit(path, syntax)` で Python 以外の言語にも使えます。`syntax` には、色分け・スニペット・自動インデントを指定します (`cardgcalc.editor.Syntax` を参照)。

インストール (PC から USB で転送):

```sh
tools/plugin.sh install plugins/basic      # .py を .mpy にコンパイルして /plugins/basic に転送し、再起動
tools/plugin.sh install-py plugins/basic   # .py のまま転送する (デバッグ用)
tools/plugin.sh build plugins/basic        # build/plugins/basic に .mpy を作る (SD カードにコピーする場合)
tools/plugin.sh remove basic               # 実機から削除
```

`build/plugins/basic` を SD カードの `/plugins/basic` にコピーしても使えます。ファイルアプリで本体の `/plugins` にコピーしても使えます。.mpy は .py より読み込みが速く、使う RAM も少なくなります。RAM のヒープは 176KB しかないので、大きいプラグインは .mpy にしてください。

Settings → Plugins では、プラグインの有効・無効の切り替え、情報の表示、削除ができます。

## BASIC (サンプルプラグイン)

`plugins/basic` は、行番号を使わない構造化 BASIC のインタプリタです。`tools/plugin.sh install plugins/basic` でインストールすると、ホーム画面に「BASIC」が加わります。

- 起動するとダイレクトモードになります。
  - 命令 (`PRINT 2^10`、`x = 5`) や式 (`x * 2`) を入力すると、すぐに実行します。
  - 読み込んだプログラムの変数・SUB・FUNCTION も使えます。
- コマンド:
  - `FILES`: プログラムの一覧。実行・編集・削除・新規作成ができます。
  - `EDIT 名前`: エディタで開きます。エディタで ctrl+r を押すと実行します。
  - `RUN [名前]`、`LOAD 名前`、`LIST`、`NEW`、`HELP`
  - `BYE` または空行で Esc: 終了します。
- 実行中のプログラムは、Esc か ctrl+c で中断できます。
- プログラムは `/programs/*.bas` (と `/sd/programs/*.bas`) に保存します。
  - 初回起動時に、サンプル (hello, primes, guess, hanoi, graphics, plot) をコピーします。
  - ファイルアプリで .bas を選んだときも、「開くアプリ: BASIC」から実行・編集できます。

```basic
' 素数を数える
FUNCTION isprime(n)
  LOCAL d
  IF n < 2 THEN RETURN 0
  FOR d = 2 TO SQR(n)
    IF n MOD d = 0 THEN RETURN 0
  NEXT
  RETURN -1
END FUNCTION

count = 0
FOR n = 2 TO 1000
  IF isprime(n) THEN count = count + 1
NEXT
PRINT count; " primes"
```

言語の概要 (詳しくは BASIC の `HELP`):

- **書き方**: 大文字と小文字は区別しません。`:` で 1 行に複数の命令を書けます。`'` か `REM` でコメントです。
- **変数**: 宣言せずに使えます。`$` で終わる名前の初期値は `""`、それ以外は 0 です。値は数値か文字列です (整数と倍精度の実数)。
  - 配列は `DIM a(10), m(3, 3)` で作り、添字は 0〜n です。
  - 変数はグローバルです。SUB・FUNCTION の引数と、`LOCAL` で宣言した変数だけがローカルです。
- **制御構造**:
  - `IF ... THEN ... ELSEIF ... ELSE ... END IF` と、1 行の `IF c THEN 文 ELSE 文`
  - `FOR ... TO ... STEP ... NEXT`、`WHILE ... WEND`
  - `DO [WHILE|UNTIL] ... LOOP [WHILE|UNTIL]`
  - `SELECT CASE` (`CASE 1, 2`、`CASE 3 TO 5`、`CASE IS > 9`、`CASE ELSE`)
  - `EXIT FOR/WHILE/DO/SUB/FUNCTION`
- **SUB / FUNCTION**: 再帰呼び出しができます (深さは FUNCTION で約 19 段、SUB で約 40 段まで)。値は `RETURN 式` か `関数名 = 式` で返します。
- **ラベル**: `名前:` か行番号を付けられ、`GOTO`、`GOSUB ... RETURN` で使えます。
- **そのほかの命令**: `DATA` / `READ` / `RESTORE`、`INPUT`、`CONST`、`SWAP`、`RANDOMIZE`、`SLEEP`、`CLS`、`END`、`STOP`
- **演算子**: `^`、`* /`、`\` (整数除算)、`MOD`、`+ -`、`&` (文字列として連結)、比較、`NOT AND OR XOR`。真は -1、偽は 0 です。
- **グラフィックス**:
  - 命令: `GCLS`、`COLOR`、`PSET`、`LINE`、`BOX`、`CIRCLE`、`GPRINT`
  - 色は `RGB(r,g,b)` か `"red"` などの名前で指定します。
  - キー入力は `INKEY$`、`WAITKEY$`、`KEYDOWN("a")` で読みます。
- **関数**: 数学 (`SIN` `SQR` `LOG` `ROUND` `RND` など)、文字列 (`LEFT$` `MID$` `INSTR` `STR$` `VAL` など)、`TIMER` `TICKS`
- **エラー表示**: 行番号付きで「3 行目: 0 で割りました」のように表示します。

インタプリタの中心部分 (`baslang.py`) は画面に依存しないので、ホストでテストできます (`tests/test_basic.py`)。

## 日本語表示

Settings の「Language / 言語」で English / 日本語 を切り替えると、メニューや画面の表示がすぐに切り替わります。

- **フォント**: 漢字と仮名は 8×12 ドットの [k8x12L](https://littlelimit.net/k8x12.htm) (JIS 第一・第二水準、7,075 字) で表示します。
  - 英数字は従来のフォントのままで、足りない文字だけを日本語フォントで描きます。
  - フォントのデータはフラッシュに置いたまま参照するので、RAM はほとんど使いません。
- **スクリプト**: Python スクリプトの `print("こんにちは")` や `cardgcalc.text()` でも、日本語をそのまま表示できます。
  - キーボードから日本語は入力できません。日本語はファイルに書いて取り込んでください。
- **翻訳の追加・修正**: `lang/*.tsv` (`英語<TAB>日本語`) を編集し、`python3 tools/mklang.py` で `src/cardgcalc/lang_ja.py` を生成します。
  - 翻訳の無い文字列は英語のまま表示されます。

## ハードウェア (Cardputer-Adv)

| 機能 | ピン |
|---|---|
| LCD ST7789V2 240×135 | SCK 36, MOSI 35, DC 34, CS 37, RST 33, BL 38 (SPI2) |
| キーボード TCA8418 | I2C SDA 8, SCL 9, INT 11 (0x34) |
| microSD | SCK 40, MOSI 14, MISO 39, CS 12 (SPI3、`/sd` にマウント) |
| Grove | G2 (黄), G1 (白) |
| EXT ヘッダ | G3, G4, G6, G5, G13, G15 (G40/G14/G39 は SD と共用、G8/G9 は内部 I2C) |
| バッテリー電圧 | G10 (ADC, 1/2 分圧) |

## ビルドと書き込み

必要なもの: ESP-IDF v5.5.x (v5.5.4 で確認)、Python 3 (esptool、mpremote、Pillow)。

```sh
git clone --recurse-submodules https://github.com/MinoruInachi/card-gcalc.git
cd card-gcalc
tools/setup.sh                    # submodule の MicroPython v1.29.0 と ulab 6.12.1 を deps/ に取得し、mpy-cross と unix 版 (ulab 入り) をビルド
IDF_PATH=/path/to/esp-idf firmware/build.sh
firmware/flash.sh                 # /dev/cu.usbmodem* に書き込む
```

- MicroPython と ulab は git submodule (`deps/micropython`、`deps/ulab`) です。`--recurse-submodules` を付けずに clone した場合も、`tools/setup.sh` が取得します。
  - パッチを当てると `deps/micropython` の作業ツリーが変更されますが、`.gitmodules` の `ignore = dirty` により、親リポジトリの `git status` には表示されません。
- ulab は C モジュールとして組み込みます。標準の -O2 では約 1.7MB 増えてアプリ領域に入らないため、ulab だけ -Os でコンパイルしています (増加は約 150KB)。
- `firmware/patches/` にある MicroPython へのパッチは、ビルド時に自動で適用されます。
  - mpy-tool が inf を含む float 定数を frozen できるようにする修正
  - esp32 ポートで、ボード側から倍精度を指定できるようにする修正
  - `<` `>` などの比較で、左辺の型が対応していなければ右辺の型で逆向きに比較する修正 (`0 < D` のような比較のため)
- REPL は ESP32-S3 内蔵の USB-Serial/JTAG を使います。そのため esptool がボタン操作なしでリセットし、書き込みモードに入れます。
  - 別のファームウェアから最初に書き込むときは、ダウンロードモードに手動で入れてください。電源 OFF・USB を抜いた状態から、G0 を押したまま USB を接続します。
  - USB 給電中は、電源スイッチを切ってもリセットされません。
- セーフモード: 起動直後のスプラッシュ表示中に G0 または `` ` `` を押すと、電卓を起動せずに REPL に留まります。
- `/main_user.py` があれば、電卓の代わりにそれを実行します。

フラッシュは、アプリ 3MB と FAT ファイルシステム約 4.9MB に分けています。データは `/data/*.json` に、プログラムは `/programs` に保存されます。

## 開発

```sh
M=deps/micropython/ports/unix/build-standard/micropython
# ホストのシミュレータ: キー操作のスクリプトを流し、@name で画面を保存する
$M tools/sim.py cardgcalc.app:main '1 "1+2×3" ENTER opt+q "2" ENTER @calc' sim_out
python3 tools/simshot.py sim_out 3        # sim_out/*.png を生成
# 実機で同じスクリプトを実行し、フレームバッファを PNG として取得する
python3 tools/devsim.py cardgcalc.app:main '2 F6 #500 @graph' dev_out
# 再ビルドせずに試す: src/cardgcalc を実機の /cardgcalc にコピーすると、frozen 版より優先される
tools/dev.sh push src/cardgcalc/apps/calc.py && tools/dev.sh reset
tools/dev.sh clean                        # 上書き用のコピーを削除する
# テスト
for t in tests/test_*.py; do $M -X heapsize=8M $t; done   # bcd、式、ソルバ、グラフ、方程式・行列、統計、BASIC
```

ディレクトリ構成:

```
firmware/            ボード定義 (CARD_GCALC)、C モジュール (ncore、bcd、ulab の組み込み設定)、パッチ、build/flash スクリプト
src/main.py          起動処理 (frozen)
src/cardgcalc/       電卓本体とスクリプト用 API (__init__.py): hal (LCD/キーボード)、gfx、ui、keymap、calc/ (式エンジン、数値計算)、apps/
src/turtle.py ...    スクリプト用モジュール (turtle, matplotlib)
plugins/basic/       サンプルプラグイン (BASIC インタプリタ)
tools/               フォント変換 (mkfont, mkfont_jp)、翻訳表の生成 (mklang)、シミュレータ、開発用スクリプト、プラグインの転送 (plugin.sh)
lang/                翻訳表 (英語<TAB>日本語)
tests/               ホスト用テスト
```

## ライセンス

MIT (LICENSE)。フォント (src/cardgcalc/fonts) のうち、英数字は X11 misc-fixed (パブリックドメイン)、日本語 (jp8x12.py) は k8x12L (© Num Kadoma) から変換したものです。k8x12 は「改変の有無・商用利用を問わず、自由に利用・複製・再配布できる」フリーソフトウェアです。ファームウェアに組み込む ulab (submodule の deps/ulab) は MIT ライセンスです。
