# card-gcalc

[日本語](README_ja.md) · **[User manual](doc/README.md)**

Firmware that turns the M5Stack [Cardputer-Adv](https://docs.m5stack.com/en/core/Cardputer-Adv) or [Cardputer](https://docs.m5stack.com/en/core/Cardputer) into a graphing calculator, built on MicroPython.

The two models read their keyboards differently, so there is a separate firmware image for each (`card-gcalc-adv-vX.Y.bin` and `card-gcalc-cardputer-vX.Y.bin`). Everything else, including saved data, programs and plugins, is the same.

- At startup an icon menu lets you choose from 13 apps
- The calculator apps compute in 15-digit decimal (equivalent to BCD): `0.1+0.2-0.3` is 0 and `sin(π)` is 0
- Floats in Python scripts are double precision (the stock MicroPython esp32 port uses single precision)
- Write, edit and run Python programs (editor, REPL, graphics API, and the numpy-compatible ulab)
- Read and write microSD cards, and drive GPIO (Grove and the expansion header)
- Add apps with plugins, without reflashing the firmware (a BASIC interpreter is included as a sample)
- Switch the display language between English and Japanese (Settings → Language / 言語)

## Apps

| # | App | Japanese label | Description |
|---|---|---|---|
| 1 | **Calc** | 計算 | Calculation screen with history. Fractions and mixed numbers typed and shown in stacked form, calculated exactly (`1/3+1/6` → `1/2`), variables (`→A` / `A=…`), Ans, exact display toggle (fractions, π, √), Deg/Rad/Gra, Norm/Fix/Sci/Eng, complex numbers |
| 2 | **Graph** | グラフ | Y1–Y6 (y=f(x), polar r=f(θ), parametric). Pan, zoom, trace. Analysis (roots, minimum/maximum, intersections, y(x), x(y), dy/dx, shaded ∫dx) |
| 3 | **3D Graph** | 3Dグラフ | Z1–Z3 (z=f(x,y), parametric, templates (line, plane, sphere, cylinder, cone), solids of revolution about the X and Y axes). Rotate, zoom, view along an axis, auto-rotate, trace. Analysis (cross sections, intersection points and lines, relative position) |
| 4 | **Table** | 数表 | Table of function values. Adjustable start and step, scrolls without limit |
| 5 | **Equation** | 方程式 | Polynomials of degree 2–4 (complex roots and exact forms), systems of 2–4 linear equations, solver (all solutions of f(x)=g(x) in a range) |
| 6 | **Stats** | 統計 | Lists L1–L3, one- and two-variable statistics, regression (linear, quadratic, exponential, logarithmic, power), scatter plots, histograms, box plots, probability distributions (normal, binomial, Poisson) |
| 7 | **Matrix** | 行列 | Matrices A–F (up to 6×6). det, inverse, transpose, rank, RREF, add/subtract/multiply, powers, Ax=b |
| 8 | **Base Conv** | 進数計算 | DEC/HEX/OCT/BIN, 8/16/32/64-bit, signed or unsigned, AND/OR/XOR/NOT/NAND/NOR/XNOR/SHL/SHR/MOD |
| 9 | **Python** | Python | Script list (/programs and /sd/programs), editor, run |
| 10 | **Shell** | シェル | Python REPL (history, multi-line blocks) |
| 11 | **Files** | ファイル | File operations on flash and SD (view, copy/move, delete, rename, mkdir, mount/unmount SD) |
| 12 | **GPIO** | GPIO | IN / OUT / ADC / PWM on G1/G2 (Grove) and G3/G4/G5/G6/G13/G15 (EXT), I2C scan |
| 13 | **Settings** | 設定 | Angle unit, display format, complex numbers, brightness, SD auto-mount, plugin management, memory info, reset |

Installed plugins appear after Settings.

## 3D Graph

Draws up to three graphs (Z1–Z3) at once.

- Types (F2 in the list):
  - Z= : enter `z=f(x,y)` in terms of x and y
  - Parametric: enter X(s,t), Y(s,t), Z(s,t) in terms of s and t. Their ranges come from S and T in the view window
  - Line: a point and a vector, or two points
  - Plane: aX+bY+cZ=d, a point and two vectors, or three points
  - Sphere: center and radius, or X²+Y²+Z²+aX+bY+cZ+d=0
  - Cylinder, cone: radius, height (Z range), center (the axis is parallel to the Z axis)
  - Solid of revolution about the X or Y axis: `y=f(x)` rotated over the x range (Xmin–Xmax)
- List: Enter edits the expression or values, F1 toggles drawing, F3 color, F4 view window (Xmin–Zmax, grid, S and T, angles θ and φ, show labels, axes, bounding box and mesh lines), F5 delete, F6 draw
- Graph screen:
  - The arrow keys (`;` `.` `,` `/`) rotate up, down, left and right; `+` / `-` zoom in and out
  - F1 Trace: the arrows move a point over the mesh and show its X, Y and Z values (computed exactly in decimal). F2 / F3 switch the target graph, and Enter lets you type coordinates
  - F2 Zoom: zoom in, zoom out, view along the X, Y or Z axis, original view
  - F4 Analysis:
    - Cross section: draws the cut made by the plane X=c, Y=c or Z=c (F1 / F2 move the plane, Enter types a value)
    - Intersection: for combinations of lines, planes and spheres, finds the intersection point, the equation of the intersection line, or the center and radius of the intersection circle
    - Relative position: tells whether two lines, two planes, or a line and a plane intersect, are perpendicular, parallel, skew or identical
  - F5 Auto-rotate: rotates two full turns horizontally or vertically (press any key to stop)
- Surfaces are filled with shading based on their orientation and clipped to the view box. The mesh density is set by grid (2–50)

## Precision (decimal arithmetic)

Numbers in the calculator apps (Calc, Graph, 3D Graph, Table, Equation, Stats, Matrix) are decimal floating-point numbers, as on a scientific calculator.

- The mantissa has 15 decimal digits and the exponent ranges over ±99. Every operation rounds to 15 digits. Normally 10 digits are displayed.
  - Out-of-range results raise an error (Math error); values smaller than 1E-99 become 0
- Numbers that can be written exactly in decimal are handled without error: `0.1+0.2-0.3` is 0 and `1-0.9` is 0.1
- On the Calc screen, fractions are calculated exactly (`src/cardgcalc/calc/frac.py`): `1/3×3` is exactly 1 and `1/7+1/13` is `20/91`
- Functions (√, ln, sin and so on) are computed to 18 digits and then rounded to 15. Any error is within one unit in the 15th digit
- Trigonometric functions:
  - In degrees and grads the period is reduced exactly in decimal, so `sin(180)` and `cos(90)` are 0
  - In radians, arguments entered as multiples of π (`sin(π)`, `cos(π/2)`, `tan(2π)` and so on) are treated as exact multiples
- Complex numbers are decimal in both the real and imaginary parts: `e^(iπ)` is -1 and `i^2` is -1
- Only the gamma function and the error function (used by the normal distribution in Stats, for example) use double-precision floats internally; their results are rounded to 15 digits
- Numbers in Python scripts (Python, Shell) are ordinary floats. The calculator's decimal numbers are implemented in the C module `bcd` (`firmware/cmodules/bcd`)
  - The mantissa is stored as a binary integer rather than as 4-bit BCD digits, but computation and rounding are done in decimal, so the results are the same as BCD

## Keys

### Common

| Key | Action |
|---|---|
| `fn` + `;` `.` `,` `/` | ↑ ↓ ← → (on screens without text input, `;` `.` `,` `/` alone also act as arrows) |
| `fn` + `` ` `` | ESC / back |
| `fn` + `1`–`6` | F1–F6 (soft keys at the bottom of the screen) |
| `fn` + `BS` | Forward delete (DEL) |
| `fn` + `-` / `=` | Start / end of line |
| `fn` + `[` / `]` | Page up / down |
| `fn` + `h` | Keymap help |

Modifier keys (`shift` `ctrl` `opt` `alt` `fn`) pressed and released on their own apply to the next key only (latch). Pressing one again locks it, and pressing it once more releases it. The state is shown in the status bar.

### Math input (`opt` / `alt`)

| Key | `opt` | `alt` |
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
| = / 8 / / / 5 / 9 / . | → × ÷ % ( , (/ is a fraction on the Calc screen) | — ∞ mixed number (Calc screen) — — — |

Examples: `2sin(π/6)`, `x²-3x+2`, `3→A`, `A(A+1)`, `∫(x²,0,3)`, `d/dx(x³,2)`, `Σ(k²,k,1,10)`, `solve(x²-2,1)`, `(-8)^(1/3)` (= -2), `e^(iπ)` (-1 in complex mode).
Implicit multiplication (`2x`, `3(x+1)`, `(a)(b)`) is supported. Closing parentheses may be omitted.

## Python

Scripts are saved as `/programs/*.py`. The first time you open the Python app, if `/programs` has no .py files, samples (hello, primes, plot, turtle_star, blink, chart, ulab_demo) are created.

- Editor: `ctrl+s` save, `ctrl+r` run, `ctrl+f` find, `ctrl+g` go to line, `ctrl+k` cut line, `ctrl+u` paste, `ctrl+z` undo, `ctrl+d` duplicate line, Tab / Shift+Tab indent
- ESC (`fn`+`` ` ``) or Ctrl+C interrupts a running script, even a loop like `while True: pass`
- `print` / `input()` are connected to the on-screen console

Modules available to scripts:

- `cardgcalc`: this device's API for the screen, keyboard, GPIO, RGB LED and more (next section)
- `turtle`: forward, left, circle, color, penup and so on
- `matplotlib.pyplot`: plot, scatter, bar, hist, axis, grid, text, show
  - Data can be lists, tuples or ulab ndarrays
  - In `plot(x, Y)`, if Y is a 2-D array each column is drawn as a separate line
- `ulab`: numpy / scipy compatible array module ([ulab](https://github.com/v923z/micropython-ulab) 6.12.1, double precision, up to 2 dimensions)
  - `from ulab import numpy as np`, `from ulab import scipy`
  - Array creation (`array`, `linspace`, `arange`, `zeros` …), element-wise operations and math functions, statistics (`mean`, `std`, `max` …), `linalg` (`inv`, `det`, `dot` …), `fft`, `polyfit` / `polyval`, `scipy.optimize` / `integrate` and more

```python
from ulab import numpy as np
import matplotlib.pyplot as plt
x = np.linspace(0, 4 * np.pi, 200)
plt.plot(x, np.sin(x) * np.exp(-x / 6))
plt.grid(True)
plt.show()
```
- Standard MicroPython modules such as `machine` work as usual

### The cardgcalc module

```python
import cardgcalc
cardgcalc.cls(); cardgcalc.line(0, 0, 239, 134, cardgcalc.RED); cardgcalc.text("hi", 10, 10, cardgcalc.YELLOW, font="large"); cardgcalc.show()
k = cardgcalc.wait_key()            # "a", "ENTER", "UP" ...
cardgcalc.plot(lambda x: x*x, -3, 3)
cardgcalc.pin_out(cardgcalc.G1, 1); v = cardgcalc.analog(cardgcalc.G2); cardgcalc.pwm(cardgcalc.G1, 1000, 50); i2c = cardgcalc.i2c_grove()
```

#### Screen

The screen is 240×135 pixels with the origin (0, 0) at the top left. Drawing goes to a screen buffer, which is copied to the display automatically while a script runs. Call `show()` to update the display immediately.

| API | Description |
|---|---|
| `W` / `width`, `H` / `height` | Screen width (240) and height (135) |
| `cls(c=BLACK)` / `clear(c=BLACK)` | Fill the whole screen with color c |
| `pixel(x, y)` / `pixel(x, y, c)` | Return a pixel's color (internal color value) / draw a pixel |
| `set_pixel(x, y, c)` | Draw a pixel |
| `get_pixel(x, y)` | Return a pixel's color as an `(r, g, b)` tuple |
| `line(x0, y0, x1, y1, c=WHITE)` | Line |
| `hline(x, y, w, c=WHITE)`, `vline(x, y, h, c=WHITE)` | Horizontal and vertical lines |
| `rect(x, y, w, h, c=WHITE)`, `fill_rect(x, y, w, h, c=WHITE)` | Rectangle outline, filled rectangle |
| `circle(x, y, r, c=WHITE, fill=False)` | Circle (center x, y, radius r) |
| `ellipse(x, y, rx, ry, c=WHITE, fill=False)` | Ellipse |
| `poly(points, c=WHITE, fill=False)` | Polygon; points is `[(x, y), ...]` |
| `text(s, x, y, c=WHITE, bg=None, font="normal")` | Draw a string and return the x coordinate where it ends. bg=None means a transparent background. Japanese text is supported |
| `text_width(s, font="normal")` | Width of a string in pixels |
| `draw_string(s, x, y, c=(0,0,0), bg=(255,255,255))` | Draw a string in the "medium" font with a background |
| `show()`, `wait_vblank()` | Copy what has been drawn to the display now |
| `brightness(pct)` | Backlight brightness (0–100 %) |

- Fonts (`font=`): `"small"` 5×8, `"normal"` 6×10, `"medium"` 6×13, `"large"` 10×20. Japanese is drawn at 8×12 in every font.
- Colors: any argument that takes a color accepts any of the following.
  - A value returned by `color(r, g, b)` (each 0–255)
  - An `(r, g, b)` tuple
  - A color name: `"black"` `"white"` `"red"` `"green"` `"blue"` `"yellow"` `"cyan"` `"magenta"` `"orange"` `"gray"` `"grey"` `"purple"` `"brown"` `"pink"`
  - A color constant: `BLACK` `WHITE` `RED` `GREEN` `BLUE` `YELLOW` `CYAN` `MAGENTA` `ORANGE` `GRAY` `GREY`
- `color()` also accepts a tuple or a name, as in `color((r, g, b))` or `color("red")`.

#### Keyboard

| API | Description |
|---|---|
| `get_key()` | Return the pressed key as a string, or `None` if no key was pressed (does not wait) |
| `wait_key()` | Wait for a key press and return the key as a string |
| `key_down(name)` / `keydown(name)` | `True` if the key is held down right now (for detecting simultaneous keys in games) |
| `keys_down()` | The set of keys held down right now |

- Strings returned by `get_key()` / `wait_key()`:
  - Character keys return the character typed (`"a"`, `"A"`, `"1"`, `"!"`, `" "` and so on)
  - `"ENTER"` `"BS"` `"TAB"`
  - With fn: `"UP"` `"DOWN"` `"LEFT"` `"RIGHT"` `"ESC"` `"DEL"` `"F1"`–`"F10"` `"HOME"` `"END"` `"PGUP"` `"PGDN"`
- Key names for `key_down()`:
  - The character on the key top (lowercase, unshifted): `"a"`, `"1"`, `";"` and so on
  - `"ENTER"` `"BS"` `"TAB"` `"SPACE"` `"ESC"` (the `` ` `` key)
  - `"UP"` `"DOWN"` `"LEFT"` `"RIGHT"`: the `;` `.` `,` `/` keys
  - Modifiers: `"SHIFT"` `"FN"` `"CTRL"` `"OPT"` `"ALT"`
- Key-name constants `KEY_*` can be used too, as in `key_down(KEY_OK)`. Examples: `KEY_UP` `KEY_DOWN` `KEY_LEFT` `KEY_RIGHT` (arrows), `KEY_OK` / `KEY_EXE` (Enter), `KEY_BACK` (`` ` ``), `KEY_BACKSPACE`, `KEY_SHIFT`, `KEY_ALPHA` (alt), `KEY_ZERO`–`KEY_NINE`, `KEY_PLUS`, `KEY_MINUS`
- Pressing ESC (`fn`+`` ` ``) or Ctrl+C while a script runs interrupts it.

#### Time and power

| API | Description |
|---|---|
| `sleep(s)`, `sleep_ms(ms)` | Wait (the break key and screen updates keep working while waiting) |
| `ticks_ms()` | Millisecond counter |
| `battery()` | Battery level (%) |

#### Graphs

| API | Description |
|---|---|
| `plot(f, xmin=-10, xmax=10, ymin=None, ymax=None, c=None, wait=True)` | Draw y=f(x) over the whole screen. If ymin / ymax are omitted the vertical range is chosen automatically. With wait=True it waits for a key press |

#### GPIO

| API | Description |
|---|---|
| `G1` `G2` (Grove), `G3` `G4` `G5` `G6` `G13` `G15` (EXT header), `PINS` | Pin number constants and a list of them |
| `pin_out(p, v=None)` | Make p an output and write v (0 / 1). Returns a `machine.Pin` |
| `pin_in(p, pull=None)` | Make p an input and return its value (0 / 1). pull is `None`, `"up"` or `"down"` |
| `analog(p)` | Voltage on p (V, 0 to about 3.1) |
| `pwm(p, freq=1000, duty=50)` | PWM output (frequency in Hz, duty in %). `duty=None` stops it |
| `tone(p, freq, ms)` | Play a tone for ms milliseconds on a piezo buzzer or similar connected to p |
| `i2c_grove(freq=100000)` | I2C on the Grove port (SDA=G2, SCL=G1) as a `machine.SoftI2C` |

#### RGB LED

| API | Description |
|---|---|
| `led(r, g, b)`, `led(c)` | Light the built-in RGB LED. c is an `(r, g, b)` tuple, a colour name or a constant such as `RED` |
| `led(None)` / `led_off()` | Turn it off |
| `led()` | Current colour as `(r, g, b)` |
| `led_brightness(pct=None)` | LED brightness (0–100 %) |

The LED is turned off when the script ends.

## Plugins

Plugins add apps without reflashing the firmware. A plugin is a folder in `/plugins/<name>/` on flash or `/sd/plugins/<name>/` on the SD card. Plugins appear on the home screen after the built-in apps.

```
/plugins/basic/
  plugin.json        manifest
  basic.mpy          entry module (run() starts the app)
  baslang.mpy        other modules and data files can live here too
  examples/...
```

Example `plugin.json`:

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

| Key | Description |
|---|---|
| `api` | Plugin API version the plugin targets. The plugin is not loaded if this is newer than the firmware's version (`cardgcalc.plugins.API`, currently 1) |
| `name` / `name_ja` | Home-screen label (`name_ja` when the display language is Japanese) |
| `module` | Entry module name. Defaults to the folder name |
| `icon` / `glyph` | Icon. `icon` names a built-in icon (`calc`, `graph` and so on); `glyph` is 1–4 characters drawn on the tile |
| `color` | Tile color `[r, g, b]` |
| `files` | File extensions the plugin handles. "Open with" in the Files app calls the entry module's `open_file(path)` |
| `description` / `description_ja` | Description shown on the info screen in Settings → Plugins |

Writing the entry module:

- Define `run()`. Return from it when the app is done.
- While the plugin runs, its folder is first on `sys.path`, so modules in the same folder can be imported directly.
- `cardgcalc.plugins.current` is the plugin's own manifest (`dir` holds the folder path).
- When the plugin returns, the modules loaded from its folder are unloaded.
- Exceptions are shown on the screen.
- The firmware's own modules can be used directly.
  - `cardgcalc.hal`: keyboard and LCD
  - `cardgcalc.gfx`, `cardgcalc.ui`: menus, input fields, messages
  - `cardgcalc.console`: scrolling text screen
  - `cardgcalc.editor`: the editor
  - `cardgcalc.runner`: break key and automatic screen updates
  - `cardgcalc.storage`, `cardgcalc` (the script API)
- `cardgcalc.plugins.translator({"English": "日本語", ...})` makes a translation function `T()` for the plugin.
- `cardgcalc.editor.edit(path, syntax)` uses the editor for languages other than Python. `syntax` provides the highlighting, snippets and auto-indent rules (see `cardgcalc.editor.Syntax`).

Installing (transfer from a PC over USB):

```sh
tools/plugin.sh install plugins/basic      # compile .py to .mpy, copy to /plugins/basic and restart
tools/plugin.sh install-py plugins/basic   # copy the .py sources as they are (for debugging)
tools/plugin.sh build plugins/basic        # build .mpy files in build/plugins/basic (to copy to an SD card)
tools/plugin.sh remove basic               # delete from the device
```

You can also copy `build/plugins/basic` to `/plugins/basic` on the SD card, or copy it to `/plugins` on the device with the Files app. .mpy files load faster and use less RAM than .py files. The RAM heap is only 176KB, so compile large plugins to .mpy.

Settings → Plugins enables or disables plugins, shows their info and deletes them.

## BASIC (sample plugin)

`plugins/basic` is an interpreter for a structured BASIC without line numbers. Install it with `tools/plugin.sh install plugins/basic` and "BASIC" appears on the home screen.

- It starts in direct mode.
  - Statements (`PRINT 2^10`, `x = 5`) and expressions (`x * 2`) run as soon as you enter them.
  - Variables, SUBs and FUNCTIONs of the loaded program are available too.
- Commands:
  - `FILES`: list of programs; run, edit, delete or create one.
  - `EDIT name`: open in the editor. Press ctrl+r in the editor to run.
  - `RUN [name]`, `LOAD name`, `LIST`, `NEW`, `HELP`
  - `BYE`, or Esc on an empty line: quit.
- Esc or ctrl+c interrupts a running program.
- Programs are saved as `/programs/*.bas` (and `/sd/programs/*.bas`).
  - Samples (hello, primes, guess, hanoi, graphics, plot) are copied at first start.
  - Selecting a .bas file in the Files app also lets you run or edit it with "Open with: BASIC".

```basic
' Count primes
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

Language overview (see `HELP` in BASIC for details):

- **Syntax**: case-insensitive. `:` separates statements on one line. `'` or `REM` starts a comment.
- **Variables**: used without declaration. Names ending in `$` start as `""`, others as 0. Values are numbers or strings (integers and double-precision reals).
  - Arrays are created with `DIM a(10), m(3, 3)`; indices run from 0 to n.
  - Variables are global. Only SUB/FUNCTION parameters and variables declared with `LOCAL` are local.
- **Control structures**:
  - `IF ... THEN ... ELSEIF ... ELSE ... END IF`, and the single-line `IF c THEN stmt ELSE stmt`
  - `FOR ... TO ... STEP ... NEXT`, `WHILE ... WEND`
  - `DO [WHILE|UNTIL] ... LOOP [WHILE|UNTIL]`
  - `SELECT CASE` (`CASE 1, 2`, `CASE 3 TO 5`, `CASE IS > 9`, `CASE ELSE`)
  - `EXIT FOR/WHILE/DO/SUB/FUNCTION`
- **SUB / FUNCTION**: recursion is supported (up to about 19 levels for FUNCTION and about 40 for SUB). Return a value with `RETURN expr` or `name = expr`.
- **Labels**: `name:` or a line number; used with `GOTO` and `GOSUB ... RETURN`.
- **Other statements**: `DATA` / `READ` / `RESTORE`, `INPUT`, `CONST`, `SWAP`, `RANDOMIZE`, `SLEEP`, `CLS`, `END`, `STOP`
- **Operators**: `^`, `* /`, `\` (integer division), `MOD`, `+ -`, `&` (string concatenation), comparisons, `NOT AND OR XOR`. True is -1 and false is 0.
- **Graphics**:
  - Statements: `GCLS`, `COLOR`, `PSET`, `LINE`, `BOX`, `CIRCLE`, `GPRINT`
  - Colors are given as `RGB(r,g,b)` or a name such as `"red"`.
  - Read keys with `INKEY$`, `WAITKEY$` and `KEYDOWN("a")`.
- **Functions**: math (`SIN` `SQR` `LOG` `ROUND` `RND` and others), strings (`LEFT$` `MID$` `INSTR` `STR$` `VAL` and others), `TIMER` `TICKS`
- **Errors**: shown with the line number, as in "Line 3: Division by zero".

The interpreter core (`baslang.py`) does not depend on the screen, so it can be tested on the host (`tests/test_basic.py`).

## Japanese display

Switching Settings → "Language / 言語" between English and 日本語 changes the menus and screens immediately.

- **Font**: kanji and kana are drawn with the 8×12-pixel [k8x12L](https://littlelimit.net/k8x12.htm) font (JIS levels 1 and 2, 7,075 characters).
  - Latin letters and digits keep the regular fonts; only the missing characters are drawn with the Japanese font.
  - The font data is read directly from flash, so it uses almost no RAM.
- **Scripts**: Japanese text can be displayed from Python scripts with `print("こんにちは")` or `cardgcalc.text()`.
  - Japanese cannot be typed on the keyboard. Write it in a file and load it from there.
- **Adding or fixing translations**: edit `lang/*.tsv` (`English<TAB>Japanese`) and run `python3 tools/mklang.py` to generate `src/cardgcalc/lang_ja.py`.
  - Strings without a translation are shown in English.

## Hardware

| Function | Pins |
|---|---|
| LCD ST7789V2 240×135 | SCK 36, MOSI 35, DC 34, CS 37, RST 33, BL 38 (SPI2) |
| Keyboard (Cardputer-Adv) | TCA8418 on I2C SDA 8, SCL 9, INT 11 (0x34) |
| Keyboard (Cardputer) | 74HC138 row select A0 8, A1 9, A2 11; column inputs 13, 15, 3, 4, 5, 6, 7 (pull-up, active low) |
| microSD | SCK 40, MOSI 14, MISO 39, CS 12 (SPI3, mounted at `/sd`) |
| Grove | G2 (yellow), G1 (white) |
| EXT header (Cardputer-Adv only) | G3, G4, G6, G5, G13, G15 (G40/G14/G39 are shared with SD, G8/G9 are the internal I2C). On the Cardputer these pins read the keyboard, so the GPIO app shows only G1/G2 |
| Battery voltage | G10 (ADC, 1/2 divider) |
| Backlight PWM | G38. 2 kHz on the Cardputer-Adv; 256 Hz on the Cardputer, whose backlight stays dark at 1 kHz or more |

## Building and flashing

Requirements: ESP-IDF v5.5.x (tested with v5.5.4), Python 3 (esptool, mpremote, Pillow).

```sh
git clone --recurse-submodules https://github.com/MinoruInachi/card-gcalc.git
cd card-gcalc
tools/setup.sh                    # fetch the MicroPython v1.29.0 and ulab 6.12.1 submodules into deps/, build mpy-cross and the unix port (with ulab)
IDF_PATH=/path/to/esp-idf firmware/build.sh            # Cardputer-Adv (build-CARD_GCALC)
IDF_PATH=/path/to/esp-idf firmware/build.sh cardputer  # Cardputer (build-CARD_GCALC-CARDPUTER)
firmware/flash.sh                 # flash the Cardputer-Adv build to /dev/cu.usbmodem*
firmware/flash.sh cardputer       # flash the Cardputer build
```

- `firmware/build.sh all` builds both. The single image to write at 0x0 is `deps/micropython/ports/esp32/<build dir>/firmware.bin`.
- The Cardputer build is the `CARDPUTER` variant of the `CARD_GCALC` board (`BOARD_VARIANT=CARDPUTER`). It freezes `model_cardputer/cardgcalc_board.py` instead of `model_adv/`, and `cardgcalc.hal` selects the keyboard driver from it (`hal.MODEL` is `"adv"` or `"cardputer"`).
- If the firmware for the other model is flashed by mistake, the Cardputer-Adv build stops at the splash screen with "wrong model". The Cardputer build cannot detect this, and its keyboard does not respond on a Cardputer-Adv.

- MicroPython and ulab are git submodules (`deps/micropython`, `deps/ulab`). If you cloned without `--recurse-submodules`, `tools/setup.sh` fetches them.
  - Applying the patches modifies the `deps/micropython` working tree, but `ignore = dirty` in `.gitmodules` keeps it out of the parent repository's `git status`.
- ulab is built in as a C module. At the default -O2 it adds about 1.7MB and does not fit in the app partition, so only ulab is compiled with -Os (adding about 150KB).
- The MicroPython patches in `firmware/patches/` are applied automatically during the build.
  - A fix that lets mpy-tool freeze float constants containing inf
  - A change that lets a board select double precision on the esp32 port
  - A fix so that comparisons such as `<` and `>` fall back to the reflected comparison on the right operand's type when the left operand's type does not support it (for comparisons like `0 < D`)
- The REPL uses the ESP32-S3's built-in USB-Serial/JTAG, so esptool can reset the board into download mode without pressing any buttons.
  - When flashing for the first time over different firmware, enter download mode by hand: with the power off and USB unplugged, hold G0 and plug in USB.
  - While powered over USB, turning the power switch off does not reset the board.
- Safe mode: pressing G0 or `` ` `` during the splash screen at startup stays in the REPL instead of starting the calculator.
- If `/main_user.py` exists, it runs instead of the calculator.

The flash is split into a 3MB app partition and a FAT file system of about 4.9MB. Data is saved in `/data/*.json` and programs in `/programs`.

## Development

```sh
M=deps/micropython/ports/unix/build-standard/micropython
# Host simulator: feed a key script and save the screen with @name
$M tools/sim.py cardgcalc.app:main '1 "1+2×3" ENTER opt+q "2" ENTER @calc' sim_out
python3 tools/simshot.py sim_out 3        # write sim_out/*.png
# Run the same script on the device and capture the frame buffer as PNG
python3 tools/devsim.py cardgcalc.app:main '2 F6 #500 @graph' dev_out
# Try changes without rebuilding: src/cardgcalc copied to /cardgcalc on the device takes precedence over the frozen version
tools/dev.sh push src/cardgcalc/apps/calc.py && tools/dev.sh reset
tools/dev.sh clean                        # remove the override copies
# Tests
for t in tests/test_*.py; do $M -X heapsize=8M $t; done   # bcd, expressions, fractions, solver, graph, equation/matrix, stats, BASIC
```

Directory layout:

```
firmware/            board definition (CARD_GCALC, variant CARDPUTER), C modules (ncore, bcd, ulab build config), patches, build/flash scripts
src/main.py          startup (frozen)
src/cardgcalc/       the calculator and the script API (__init__.py): hal (LCD/keyboard), gfx, ui, keymap, calc/ (expression engine, numerics), apps/
src/turtle.py ...    script modules (turtle, matplotlib)
plugins/basic/       sample plugin (BASIC interpreter)
tools/               font conversion (mkfont, mkfont_jp), translation table generator (mklang), simulator, development scripts, plugin transfer (plugin.sh)
lang/                translation tables (English<TAB>Japanese)
tests/               host tests
```

## License

MIT (LICENSE). Of the fonts in src/cardgcalc/fonts, the Latin fonts are converted from X11 misc-fixed (public domain), and the Japanese font (jp8x12.py) from k8x12L (© Num Kadoma). k8x12 is free software that "may be freely used, copied and redistributed, modified or not, including for commercial use". ulab (the deps/ulab submodule), which is built into the firmware, is under the MIT license.
