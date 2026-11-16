# Tests for the BASIC plugin interpreter core (plugins/basic/baslang.py).
#   deps/micropython/ports/unix/build-standard/micropython tests/test_basic.py
import sys

sys.path.insert(0, "plugins/basic")
from baslang import Basic, BasicError, HostIO

fails = 0


def run(src, inputs=None):
    io = HostIO(inputs, echo=False)
    b = Basic(io)
    try:
        b.load(src)
        b.run()
    except BasicError as e:
        io.text.append("ERR:%s" % e)
    except KeyboardInterrupt:
        io.text.append("BREAK:%s" % b.brk)
    return "".join(io.text)


def t(src, want, inputs=None):
    global fails
    got = run(src, inputs)
    if got != want:
        fails += 1
        print("FAIL", repr(src[:60]))
        print("  got ", repr(got))
        print("  want", repr(want))


# ---- expressions / PRINT
t('PRINT 1+2*3', "7\n")
t('PRINT 2^3^2, -2^2', "64        -4\n")
t('PRINT 7/2; " "; 7\\2; " "; -7\\2; " "; 7 MOD 3; " "; -7 MOD 3', "3.5 3 -3 1 -1\n")
t('PRINT 1/3', "0.3333333333\n")
t('PRINT 0.1+0.2', "0.3\n")
t('PRINT 1E20; " "; 1.5E-7', "1E+20 1.5E-7\n")
t('PRINT 10/4*2', "5\n")
t('PRINT &HFF; &B101', "2555\n")
t('PRINT "a";"b";', "ab")
t('PRINT "x=" & 3 & "!"', "x=3!\n")
t('? 1<2, 1=2, NOT 0, 3 AND 0, 0 OR 5', "-1        0         -1        0         -1\n")
t('PRINT "abc" + "def", "q""q"', 'abcdef    q"q\n')
t('PRINT LEN("hello"); LEFT$("hello",2); RIGHT$("hello",3); MID$("hello",2,3); MID$("hello",4)', "5helloelllo\n")
t('PRINT INSTR("hello","l"); INSTR(4,"hello","l"); UCASE$("ab"); CHR$(65); ASC("a")', "34ABA97\n")
t('PRINT STR$(1.5); VAL("2.5")*2; VAL("x"); HEX$(255); BIN$(5)', "1.550FF101\n")
t('PRINT INT(-2.5); FIX(-2.5); ABS(-3); SGN(-2); SQR(16); ROUND(2.5); ROUND(3.14159,2); ROUND(1234,-2)',
  "-3-23-1433.141200\n")
t('PRINT MIN(3,1,2); MAX(3,1,2); "["; SPACE$(2); "]"; STRING$(3,"*")', "13[  ]***\n")
t('PRINT "a"; TAB(5); "b"', "a   b\n")

# ---- variables, arrays
t('x = 5: y$ = "hi": PRINT x; y$; z; "["; w$; "]"', "5hi0[]\n")
t('LET a = 1: a = a + 1: PRINT a', "2\n")
t('DIM a(5): FOR i = 0 TO 5: a(i) = i * i: NEXT: PRINT a(5); a(2)', "254\n")
t('DIM m(2,3): m(1,2) = 7: PRINT m(1,2); m(2,3)', "70\n")
t('DIM s$(2): s$(1) = "x": PRINT "["; s$(0); "]"; s$(1)', "[]x\n")
t('DIM a(2): PRINT a(3)', "ERR:Subscript out of range (line 1)")
t('PRINT q(1)', "ERR:Array not dimensioned: q (line 1)")
t('a = 1: b = 2: SWAP a, b: PRINT a; b', "21\n")
t('CONST N = 10: PRINT N * 2', "20\n")

# ---- control flow
t('''FOR i = 1 TO 3
  PRINT i;
NEXT i
PRINT
FOR i = 10 TO 1 STEP -4: PRINT i;: NEXT
PRINT
FOR i = 1 TO 0: PRINT "never": NEXT
PRINT "i="; i''', "123\n1062\ni=1\n")
t('''FOR i = 1 TO 3
  FOR j = 1 TO 2
    PRINT i * j;
  NEXT j, i''', "122436")
t('''x = 5
IF x > 3 THEN
  PRINT "big"
ELSEIF x > 1 THEN
  PRINT "mid"
ELSE
  PRINT "small"
END IF
IF x = 1 THEN PRINT "one" ELSE PRINT "not one": PRINT "!"
IF x = 5 THEN PRINT "five": PRINT "!!"
IF x < 0 THEN PRINT "neg"
ENDIF_TEST:
IF x THEN
  PRINT "T"
ENDIF''', "big\nnot one\n!\nfive\n!!\nT\n")
t('''n = 0
WHILE n < 3
  n = n + 1
WEND
PRINT n
DO
  n = n - 1
LOOP UNTIL n <= 0
PRINT n
DO WHILE n < 4: n = n + 2: LOOP
PRINT n
DO
  n = n + 1
  IF n > 10 THEN EXIT DO
LOOP
PRINT n
FOR i = 1 TO 100
  IF i = 4 THEN EXIT FOR
NEXT
PRINT i''', "3\n0\n4\n11\n4\n")
t('''FOR k = 1 TO 6
  SELECT CASE k
    CASE 1
      PRINT "one";
    CASE 2, 3
      PRINT "two-three";
    CASE 4 TO 5
      PRINT "range";
    CASE ELSE
      PRINT "else";
  END SELECT
  PRINT ",";
NEXT''', "one,two-three,two-three,range,range,else,")
t('''SELECT CASE 50
CASE IS < 10: PRINT "small"
CASE IS >= 10: PRINT "big"
END SELECT''', "big\n")

# ---- GOTO / GOSUB / labels / line numbers
t('''i = 0
again:
i = i + 1
IF i < 3 THEN GOTO again
PRINT i
GOSUB sub1
PRINT "back"
END
sub1:
  PRINT "in sub"
  RETURN''', "3\nin sub\nback\n")
t('''10 X = 1
20 IF X > 3 THEN 50
30 X = X + 1
40 GOTO 20
50 PRINT X''', "4\n")
t('GOTO nowhere', "ERR:Label not found: nowhere (line 1)")
t('RETURN', "ERR:RETURN without GOSUB (line 1)")

# ---- SUB / FUNCTION
t('''FUNCTION fact(n)
  IF n <= 1 THEN RETURN 1
  RETURN n * fact(n - 1)
END FUNCTION
FUNCTION sq(x)
  sq = x * x
END FUNCTION
SUB show(a, b$)
  PRINT b$; a
END SUB
PRINT fact(10)
show sq(7), "sq="
CALL show(1, "one=")
show(2, "two=")''', "3628800\nsq=49\none=1\ntwo=2\n")
t('''total = 0
SUB addup(n)
  LOCAL i
  FOR i = 1 TO n
    total = total + i
  NEXT
END SUB
i = 99
addup 10
PRINT total; i''', "5599\n")
t('''FUNCTION fib(n)
  IF n < 2 THEN
    fib = n
  ELSE
    fib = fib(n - 1) + fib(n - 2)
  END IF
END FUNCTION
FOR i = 0 TO 10: PRINT fib(i);" ";: NEXT''', "0 1 1 2 3 5 8 13 21 34 55 ")
t('''SUB early(x)
  IF x > 0 THEN EXIT SUB
  PRINT "neg"
END SUB
early 1
early -1''', "neg\n")
t('''FUNCTION f(a, b)
  RETURN a + b
END FUNCTION
PRINT f(1)''', "ERR:Wrong number of arguments: f (line 4)")
t('''FUNCTION depth(n)
  RETURN depth(n + 1)
END FUNCTION
PRINT depth(1)''', "ERR:Too many nested calls (line 2)")

# ---- DATA / READ / INPUT
t('''READ a, b$, c
PRINT a; b$; c
RESTORE more
READ x
PRINT x
DATA 1, "two", -3.5
more:
DATA 42''', "1two-3.5\n42\n")
t('READ a: READ b\nDATA 1', "ERR:Out of DATA (line 1)")
t('INPUT "Name"; n$: INPUT "Age", a: PRINT n$; a + 1', "Name? Bob\nAge7\nBob8\n", ["Bob", "7"])
t('INPUT x, y: PRINT x * y', "? 1\n?Redo from start\n? 3,4\n12\n", ["1", "3,4"])
t('INPUT a', "? BREAK:1", [])

# ---- errors
t('PRINT 1/0', "ERR:Division by zero (line 1)")
t('PRINT "a" + 1', "ERR:Type mismatch (line 1)")
t('PRINT SQR(-1)', "ERR:Illegal function call (line 1)")
t('PRINT (1', "ERR:')' expected (line 1)")
t('FOR i = 1 TO 2', "ERR:FOR without NEXT (line 1)")
t('NEXT', "ERR:NEXT without FOR (line 1)")
t('x = 1\nPRINT "ok"\nx = (', "ERR:Expression expected (line 3)")
t('PRINT "abc', 'ERR:Missing closing " (line 1)')
t('x = 1 2', "ERR:Syntax error (line 1)")
t('STOP', "BREAK:1")
t('x = 1: END: PRINT "no"', "")

# ---- graphics calls are passed to the I/O object
io = HostIO(echo=False)
b = Basic(io)
b.load('COLOR RGB(255,0,0)\nPSET 1, 2\nLINE 0, 0, 10, 10, 5\nCIRCLE 5, 5, 3\nGPRINT 0, 0, "hi"\nGCLS')
b.run()
want = [("pset", 1, 2, 63488), ("line", 0, 0, 10, 10, 5), ("circle", 5, 5, 3, 63488, None),
        ("gprint", 0, 0, "hi", 63488), ("gcls", None)]
if io.calls != want:
    fails += 1
    print("FAIL graphics", io.calls)

# ---- direct mode uses the loaded program
io = HostIO(echo=False)
b = Basic(io)
b.load('FUNCTION dbl(x)\n  RETURN x * 2\nEND FUNCTION\nn = 21')
b.run()
b.immediate("PRINT dbl(n)")
b.immediate("FOR i = 1 TO 3: PRINT i;: NEXT")
try:
    b.immediate("PRINT (")
except BasicError as e:
    io.text.append("compile=%s" % e.compile)
try:
    b.immediate("PRINT 1/0")
except BasicError as e:
    io.text.append("compile=%s" % e.compile)
got = "".join(io.text)
if got != "42\n123compile=Truecompile=False":
    fails += 1
    print("FAIL direct", repr(got))

print("test_basic: %d failures" % fails)
sys.exit(1 if fails else 0)
