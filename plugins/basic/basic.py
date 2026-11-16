# BASIC plugin for card-gcalc: console (direct mode), program files,
# editor support and screen / keyboard I/O.  The language is in baslang.py.
#
# Direct mode: type a statement to run it now (PRINT 2^10, x = 5, ...), an
# expression to print its value, or a command:
#   FILES           program list (Run / Edit / Delete, New program)
#   EDIT [name]     edit a program (ctrl+r in the editor runs it)
#   RUN [name]      run the current program or load and run `name`
#   LOAD name       load a program      LIST   show the current program
#   NEW             forget the current program
#   HELP            language summary    BYE / Esc on an empty line: exit
# Programs are /programs/<name>.bas (also /sd/programs when the SD card is
# mounted).
import gc
import os
from nc import hal, gfx, ui, storage, runner, plugins, settings
from nc.console import Console
import baslang
from baslang import Basic, BasicError

JA = {
    "BASIC %s  (card-gcalc plugin)": "BASIC %s  (card-gcalc プラグイン)",
    "FILES / EDIT name / RUN name / HELP": "FILES / EDIT 名前 / RUN 名前 / HELP",
    "Esc on empty line: exit": "空行で Esc: 終了",
    "BASIC programs": "BASIC プログラム",
    "New program...": "新規プログラム...",
    "Program name": "プログラム名",
    "Bad name": "名前が不正です",
    "No program loaded": "プログラムが読み込まれていません",
    "Loaded %s (%d lines)": "%s を読み込みました (%d 行)",
    "Line %d: %s": "%d 行目: %s",
    "Break in line %d": "%d 行目で中断",
    "Break": "中断",
    "Delete %s?": "%s を削除しますか？",
    "BASIC help": "BASIC ヘルプ",
    "Syntax error": "構文エラー",
    "Expression expected": "式がありません",
    "Name expected": "名前がありません",
    "Label expected": "ラベルがありません",
    "Label not found": "ラベルが見つかりません",
    "Duplicate label": "ラベルが重複しています",
    "Duplicate name": "名前が重複しています",
    "Wrong number of arguments": "引数の数が違います",
    "Subscript expected": "添字がありません",
    "Subscript out of range": "添字が範囲外です",
    "Array not dimensioned": "配列が DIM されていません",
    "Division by zero": "0 で割りました",
    "Type mismatch": "型が違います",
    "Overflow": "オーバーフロー",
    "Out of memory": "メモリ不足",
    "Too many nested calls": "呼び出しが深すぎます",
    "Illegal function call": "関数の引数が不正です",
    "Out of DATA": "DATA が足りません",
    "RETURN without GOSUB": "GOSUB のない RETURN",
    "Unexpected character": "使えない文字",
    "Unknown SUB": "SUB がありません",
    "Bad number": "数値が不正です",
    "Parameter name expected": "引数名がありません",
    "Comparison expected": "比較演算子がありません",
    "Number or string expected in DATA": "DATA には数値か文字列を書きます",
    "LOCAL outside SUB / FUNCTION": "LOCAL は SUB / FUNCTION の中で使います",
    "Cannot read %s": "%s を読めません",
    "Missing closing \"": "\" が閉じていません",
    "Block not closed on the IF line": "IF の行でブロックが閉じていません",
}
T = plugins.translator(JA)

PROG = storage.PROGRAMS
SD_PROG = storage.SD + "/programs"
EXT = ".bas"

HELP_EN = """Statements  (':' separates statements)
 PRINT a; b, c    (? = PRINT)
   ; joins   , next column
 INPUT "Name"; n$   INPUT x
 LET x = 1   (LET is optional)
 IF c THEN ... ELSEIF c THEN ...
   ELSE ... END IF
 IF c THEN stmt ELSE stmt  (one line)
 FOR i = 1 TO 9 STEP 2 ... NEXT
 WHILE c ... WEND
 DO [WHILE|UNTIL c] ...
   LOOP [WHILE|UNTIL c]
 SELECT CASE x
   CASE 1, 2 / CASE 3 TO 5
   CASE IS > 9 / CASE ELSE
   END SELECT
 EXIT FOR|WHILE|DO|SUB|FUNCTION
 SUB s(a, b) ... END SUB
   call: s 1, 2  or  CALL s(1, 2)
 FUNCTION f(x) ... END FUNCTION
   RETURN x * 2  (or f = value)
 LOCAL v  (local in SUB/FUNCTION;
   other variables are global)
 DIM a(10), m(3, 3), s$(5)  (0..n)
 label:  GOTO label
 GOSUB label ... RETURN
 DATA 1, "a"   READ x, s$
 RESTORE [label]   CONST N = 10
 SWAP a, b   RANDOMIZE [n]
 SLEEP sec   CLS   END   STOP
 REM comment   ' comment
Graphics  240x135, (0,0) top left
 colour: RGB(r,g,b) or "red"
 GCLS [c]   COLOR c   PSET x,y[,c]
 LINE x1,y1,x2,y2[,c]
 BOX x,y,w,h[,c[,fill]]
 CIRCLE x,y,r[,c[,fill]]
 GPRINT x,y,text[,c]
Operators  (true = -1, false = 0)
 ^  * /  \\ (integer div)  MOD  + -
 & (join as text)
 = <> < > <= >=   NOT AND OR XOR
Functions
 ABS INT FIX SGN SQR EXP LOG LOG10
 SIN COS TAN ATN ATAN2 PI RND
 ROUND(x[,n]) MIN MAX BAND BOR BXOR
 LEN LEFT$ RIGHT$ MID$ INSTR VAL
 UCASE$ LCASE$ TRIM$ LTRIM$ RTRIM$
 STR$ CHR$ ASC SPACE$ STRING$
 HEX$ BIN$ SPC TAB TIMER TICKS
 INKEY$ WAITKEY$ KEYDOWN("a")
Direct mode
 FILES  EDIT [name]  RUN [name]
 LOAD name  LIST  NEW  BYE
 A statement or an expression (1+2)
 runs at once. Esc stops a program."""

HELP_JA = """命令  (':' で複数の命令を区切る)
 PRINT a; b, c    (? = PRINT)
   ; 続けて表示   , 次の桁へ
 INPUT "名前"; n$   INPUT x
 LET x = 1   (LET は省略可)
 IF c THEN ... ELSEIF c THEN ...
   ELSE ... END IF
 IF c THEN 命令 ELSE 命令  (1 行)
 FOR i = 1 TO 9 STEP 2 ... NEXT
 WHILE c ... WEND
 DO [WHILE|UNTIL c] ...
   LOOP [WHILE|UNTIL c]
 SELECT CASE x
   CASE 1, 2 / CASE 3 TO 5
   CASE IS > 9 / CASE ELSE
   END SELECT
 EXIT FOR|WHILE|DO|SUB|FUNCTION
 SUB s(a, b) ... END SUB
   呼び出し: s 1, 2 / CALL s(1, 2)
 FUNCTION f(x) ... END FUNCTION
   RETURN x * 2  (f = 値 でも可)
 LOCAL v  (SUB/FUNCTION 内の変数。
   それ以外の変数はグローバル)
 DIM a(10), m(3, 3), s$(5)  (0..n)
 ラベル:  GOTO ラベル
 GOSUB ラベル ... RETURN
 DATA 1, "a"   READ x, s$
 RESTORE [ラベル]   CONST N = 10
 SWAP a, b   RANDOMIZE [n]
 SLEEP 秒   CLS   END   STOP
 REM コメント   ' コメント
グラフィックス  240x135、(0,0) が左上
 色: RGB(r,g,b) か "red" など
 GCLS [c]   COLOR c   PSET x,y[,c]
 LINE x1,y1,x2,y2[,c]
 BOX x,y,w,h[,c[,塗り]]
 CIRCLE x,y,r[,c[,塗り]]
 GPRINT x,y,文字列[,c]
演算子  (真 = -1、偽 = 0)
 ^  * /  \\ (整数除算)  MOD  + -
 & (文字列として連結)
 = <> < > <= >=   NOT AND OR XOR
関数
 ABS INT FIX SGN SQR EXP LOG LOG10
 SIN COS TAN ATN ATAN2 PI RND
 ROUND(x[,n]) MIN MAX BAND BOR BXOR
 LEN LEFT$ RIGHT$ MID$ INSTR VAL
 UCASE$ LCASE$ TRIM$ LTRIM$ RTRIM$
 STR$ CHR$ ASC SPACE$ STRING$
 HEX$ BIN$ SPC TAB TIMER TICKS
 INKEY$ WAITKEY$ KEYDOWN("a")
ダイレクトモード
 FILES  EDIT [名前]  RUN [名前]
 LOAD 名前  LIST  NEW  BYE
 命令や式 (1+2) はすぐ実行します。
 実行中のプログラムは Esc で中断。"""


# ---- editor support ---------------------------------------------------------------
class Syntax:
    multiline = False
    snippets = {
        "p": "PRINT ", "i": "IF  THEN", "e": "END IF", "l": "ELSE", "f": "FOR i = 1 TO ",
        "n": "NEXT", "w": "WHILE ", "d": "DIM ", "s": "SUB ", "u": "FUNCTION ",
        "r": "RETURN ", "g": "GOSUB ", "t": "INPUT ", "c": "SELECT CASE ", "o": "DO",
    }
    _OPEN = ("FOR", "WHILE", "DO", "SUB", "FUNCTION", "SELECT", "CASE", "ELSE", "ELSEIF")

    def __init__(self, funcs):
        from nc import editor as E

        self.funcs = funcs
        self.C = (E.C_KW, E.C_BI, E.C_STR, E.C_NUM, E.C_COM, E.C_OP, E.C_TXT)

    def highlight(self, line, st=None):
        C_KW, C_BI, C_STR, C_NUM, C_COM, C_OP, C_TXT = self.C
        runs = []
        i = 0
        n = len(line)
        while i < n:
            c = line[i]
            if c == "'":
                runs.append((line[i:], C_COM))
                break
            if c == '"':
                j = line.find('"', i + 1)
                if j < 0:
                    j = n - 1
                runs.append((line[i: j + 1], C_STR))
                i = j + 1
                continue
            if c.isalpha() or c == "_":
                j = i + 1
                while j < n and (line[j].isalpha() or line[j].isdigit() or line[j] in "_$"):
                    j += 1
                w = line[i:j]
                u = w.upper()
                if u == "REM":
                    runs.append((line[i:], C_COM))
                    break
                runs.append((w, C_KW if u in baslang.KW else C_BI if w.lower() in self.funcs else C_TXT))
                i = j
                continue
            if c.isdigit():
                j = i + 1
                while j < n and (line[j].isdigit() or line[j] in ".eE"):
                    j += 1
                runs.append((line[i:j], C_NUM))
                i = j
                continue
            if c == " ":
                j = i + 1
                while j < n and line[j] == " ":
                    j += 1
                runs.append((line[i:j], C_TXT))
                i = j
                continue
            runs.append((c, C_OP if c in "()=+-*/\\^<>,;:&?" else C_TXT))
            i += 1
        return runs, None

    def indent_after(self, line):
        s = line.strip().upper()
        w = s.split(" ")[0] if s else ""
        if w in self._OPEN:
            return True
        return w == "IF" and s.endswith("THEN")


# ---- screen / keyboard I/O ------------------------------------------------------
class ScreenIO:
    def __init__(self, con):
        import cardgcalc

        self.con = con
        self.nc = cardgcalc
        # Polled in loops for the break key.  Not needed on the device when
        # the firmware raises KeyboardInterrupt asynchronously (ncore).
        self.check = None if hal.IS_DEVICE and runner._kbd_interrupt else runner.check

    def out(self, s):
        runner.check()
        self.con.write(s)

    def input(self, prompt):
        s = self.con.readline(prompt)
        if s is None:
            raise KeyboardInterrupt
        return s

    def cls(self):
        self.con.clear()
        self.con.suspended = False
        self.con.draw()

    def sleep(self, s):
        self.nc.sleep(s)

    def inkey(self):
        return self.nc.get_key() or ""

    def waitkey(self):
        return self.nc.wait_key()

    def keydown(self, k):
        return self.nc.key_down(k)

    def rgb(self, r, g, b):
        return self.nc.color(r, g, b)

    def _c(self, c, d):
        return d if c is None else c

    def gcls(self, c):
        self.nc.cls(self._c(c, self.nc.BLACK))

    def pset(self, x, y, c):
        self.nc.pixel(x, y, self._c(c, self.nc.WHITE))

    def line(self, x1, y1, x2, y2, c):
        self.nc.line(x1, y1, x2, y2, self._c(c, self.nc.WHITE))

    def box(self, x, y, w, h, c, fill):
        c = self._c(c, self.nc.WHITE)
        if fill:
            self.nc.fill_rect(x, y, w, h, c)
        else:
            self.nc.rect(x, y, w, h, c)

    def circle(self, x, y, r, c, fill):
        self.nc.circle(x, y, r, self._c(c, self.nc.WHITE), bool(fill))

    def gprint(self, x, y, s, c):
        self.nc.text(baslang.tostr(s), x, y, self._c(c, self.nc.WHITE))


# ---- program files ------------------------------------------------------------------
def _path(name):
    name = name.strip().strip('"').strip()
    if not name:
        return None
    if not name.lower().endswith(EXT):
        name += EXT
    return name if "/" in name else PROG + "/" + name


def _list_programs():
    out = []
    for d, tag in ((PROG, ""), (SD_PROG, "SD")):
        if tag and not storage.sd_mounted():
            continue
        try:
            names = sorted(n for n in os.listdir(d) if n.lower().endswith(EXT))
        except OSError:
            continue
        for n in names:
            out.append((n[: -len(EXT)], d + "/" + n, tag))
    return out


def _ensure_examples():
    marker = storage.path("basic_examples")
    if storage.exists(marker) or plugins.current is None:
        return
    src = plugins.current["dir"] + "/examples"
    try:
        for n in os.listdir(src):
            dst = PROG + "/" + n
            if n.endswith(EXT) and not storage.exists(dst):
                with open(src + "/" + n) as f:
                    data = f.read()
                with open(dst, "w") as f:
                    f.write(data)
        with open(marker, "w") as f:
            f.write("1")
    except OSError as e:
        print("basic examples:", e)


# ---- the app --------------------------------------------------------------------------
class App:
    def __init__(self):
        self.con = Console("BASIC")
        self.io = ScreenIO(self.con)
        self.b = Basic(self.io)
        self.path = None
        self.hist = []
        self.syntax = Syntax(self.b.bi)

    def say(self, s, color=None):
        self.con.write(s + "\n", color)

    def error(self, e):
        if self.b.col:
            self.b.out("\n")
        self.b.col = 0
        msg = e.msg
        i = msg.find(" without ")
        if i > 0 and settings.get("lang") == "ja":
            msg = "%s に対応する %s がありません" % (msg[:i], msg[i + 9:])
        else:
            msg = T(msg)
        self.say(T("Line %d: %s") % (e.line, msg) if e.line else msg, gfx.ERR)

    def title(self):
        self.con.title = "BASIC" + (" - " + self.path.split("/")[-1] if self.path else "")

    # ---- program handling ------------------------------------------------------
    def load(self, path, quiet=False):
        try:
            with open(path) as f:
                src = f.read()
        except OSError:
            self.say(T("Cannot read %s") % path, gfx.ERR)
            return False
        self.path = path
        self.title()
        n = src.count("\n") + 1
        try:
            self.b.load(src)
        except BasicError as e:
            self.error(e)
            return False
        finally:
            del src
            gc.collect()
        if not quiet:
            self.say(T("Loaded %s (%d lines)") % (path.split("/")[-1], n), gfx.DIM)
        return True

    def run_program(self, path=None):
        path = path or self.path
        if path is None:
            self.say(T("No program loaded"), gfx.ERR)
            return
        if not self.load(path, quiet=True):
            return
        self._exec(self.b.run)

    def _exec(self, fn, arg=None, direct=False):
        """Run BASIC code with break handling and graphics display.
        Returns the BasicError raised (not shown if it is a compile error
        of a direct-mode line), else None."""
        con = self.con
        runner.start(con)
        broke = False
        err = None
        try:
            fn() if arg is None else fn(arg)
        except KeyboardInterrupt:
            broke = True
            if self.b.col:
                self.b.out("\n")
            self.say(T("Break in line %d") % self.b.brk if self.b.brk else T("Break"), gfx.YELLOW)
        except BasicError as e:
            err = e
            if not (e.compile and direct):
                self.error(e)
        finally:
            runner.stop()
            if self.b.col:
                self.b.out("\n")
            self.b.col = 0
        if runner.graphics_used:
            if runner.pending and not broke:
                hal.display.show()
                hal.wait_key()
            runner.graphics_used = False
            runner.pending = False
        con.suspended = False
        gc.collect()
        return err

    def edit(self, path):
        from nc import editor

        self.path = path
        self.title()
        while True:
            r = editor.edit(path, self.syntax)
            if r != "run":
                self.load(path, quiet=True)
                return
            self.con.suspended = False
            self.run_program(path)
            self.con.wait_end()

    def files(self):
        while True:
            progs = _list_programs()
            items = [T("New program...")] + [(n, tag) for n, p, tag in progs]
            i = ui.menu(T("BASIC programs"), items)
            if i is None:
                return
            if i == 0:
                name = ui.input_line(T("Program name"), "", math=False)
                p = _path(name or "")
                if not p:
                    continue
                if not storage.exists(p):
                    with open(p, "w") as f:
                        f.write("' %s\nPRINT \"Hello\"\n" % name.strip())
                self.edit(p)
                return
            n, p, tag = progs[i - 1]
            j = ui.menu(n, ["Run", "Edit", "Delete"])
            if j == 0:
                self.con.suspended = False
                self.con.draw()
                self.run_program(p)
                return
            if j == 1:
                self.edit(p)
                return
            if j == 2 and ui.confirm(T("Delete %s?") % n):
                try:
                    os.remove(p)
                except OSError:
                    pass
                if self.path == p:
                    self.path = None
                    self.b.load("")
                    self.title()

    def listing(self):
        if self.path is None:
            self.say(T("No program loaded"), gfx.ERR)
            return
        try:
            with open(self.path) as f:
                lines = f.read().split("\n")
        except OSError:
            return
        ui.text_view(self.path.split("/")[-1], ["%3d %s" % (i + 1, l) for i, l in enumerate(lines)])

    # ---- direct mode ------------------------------------------------------------
    def command(self, line):
        """Handle a direct-mode command.  Returns False to leave the app."""
        s = line.strip()
        w = s.split(" ", 1)
        cmd = w[0].upper()
        arg = w[1].strip() if len(w) > 1 else ""
        if cmd in ("BYE", "QUIT") or s.upper() == "EXIT":
            return False
        if cmd == "RUN" and not arg.startswith("="):
            self.run_program(_path(arg) if arg else None)
        elif cmd == "EDIT" and not arg.startswith("="):
            p = _path(arg) if arg else self.path
            if p is None:
                name = ui.input_line(T("Program name"), "", math=False)
                p = _path(name or "")
            if p:
                self.edit(p)
        elif cmd == "LOAD" and arg and not arg.startswith("="):
            self.load(_path(arg))
        elif cmd in ("FILES", "DIR") and not arg:
            self.files()
        elif cmd == "LIST" and not arg:
            self.listing()
        elif cmd == "NEW" and not arg:
            self.path = None
            self.b.load("")
            self.title()
        elif cmd == "HELP" and not arg:
            ui.text_view(T("BASIC help"), (HELP_JA if settings.get("lang") == "ja" else HELP_EN).split("\n"))
        else:
            self.direct(s)
        return True

    def direct(self, s):
        e = self._exec(self.b.immediate, s, True)
        if e is None or not e.compile:
            return
        # not a statement: maybe an expression -> print its value
        e2 = self._exec(self.b.immediate, "PRINT " + s, True)
        if e2 is not None and e2.compile:
            self.error(e)

    def repl(self):
        con = self.con
        con.write(T("BASIC %s  (card-gcalc plugin)") % baslang.VERSION + "\n", gfx.ACCENT)
        con.write(T("FILES / EDIT name / RUN name / HELP") + "\n", gfx.DIM)
        con.write(T("Esc on empty line: exit") + "\n", gfx.DIM)
        while True:
            con.suspended = False
            try:
                line = con.readline("> ", self.hist)
            except KeyboardInterrupt:
                con.write("\n")
                continue
            if line is None:
                return
            if not line.strip():
                continue
            if not self.hist or self.hist[-1] != line:
                self.hist.append(line)
                if len(self.hist) > 30:
                    del self.hist[0]
            if not self.command(line):
                return
            con.draw()


def run():
    storage.ensure_dirs()
    _ensure_examples()
    App().repl()
    gc.collect()


def open_file(path):
    """Files app: open a .bas file."""
    i = ui.menu(path.split("/")[-1], ["Run", "Edit"])
    if i is None:
        return
    app = App()
    if i == 0:
        app.con.draw()
        app.run_program(path)
        app.con.wait_end()
    else:
        app.edit(path)
