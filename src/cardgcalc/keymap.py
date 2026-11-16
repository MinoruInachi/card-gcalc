# Math input layers.  opt+<key> and alt+<key> insert math tokens in any
# math input field (calculator, graph functions, table, equations ...).
#
# Tap opt / alt on its own to latch it for the next key (like SHIFT on a
# calculator); tap twice to lock.

OPT = {
    "s": "sin(", "c": "cos(", "t": "tan(",
    "l": "ln(", "g": "log(", "e": "e^(", "u": "10^(",
    "q": "√(", "r": "∛(", "w": "root(",
    "p": "π", "a": "Ans", "x": "x", "y": "y", "h": "θ", "i": "i", "k": "k",
    "f": "!", "n": "nCr(", "m": "mod(", "b": "abs(",
    "d": "d/dx(", "j": "∫(", "z": "Σ(", "v": "solve(", "o": "∏(",
    "1": "⁻¹", "2": "²", "3": "³", "6": "^", "0": "E", "8": "×", "/": "÷",
    "=": "→", "9": "(", ".": ",", "5": "%",
}

ALT = {
    "s": "sin⁻¹(", "c": "cos⁻¹(", "t": "tan⁻¹(",
    "h": "sinh(", "j": "cosh(", "k": "tanh(",
    "l": "log2(", "g": "log(", "e": "exp(",
    "q": "sqrt(", "r": "round(", "f": "floor(", "i": "int(", "d": "deg(", "u": "rad(",
    "n": "nPr(", "m": "min(", "x": "max(", "b": "gcd(", "v": "lcm(",
    "a": "atan2(", "p": "isprime(", "o": "rand()", "z": "randint(", "w": "fpart(",
    "1": "fact(", "2": "³", "3": "∛(", "8": "∞",
}

# Tokens deleted as a unit by backspace (longest first).
TOKENS = sorted(set(list(OPT.values()) + list(ALT.values()) + ["Ans"]), key=lambda s: -len(s))
TOKENS = [t for t in TOKENS if len(t) > 1]

HELP = (
    ("opt", "s sin  c cos  t tan  l ln  g log"),
    ("opt", "e e^   u 10^  q √   r ∛  w ⁿ√"),
    ("opt", "p π  a Ans  x x  y y  h θ  i i"),
    ("opt", "f !  n nCr  m mod  b abs"),
    ("opt", "d d/dx  j ∫  z Σ  o ∏  v solve"),
    ("opt", "1 ⁻¹  2 ²  3 ³  6 ^  0 E  = →"),
    ("alt", "s sin⁻¹ c cos⁻¹ t tan⁻¹"),
    ("alt", "h sinh  j cosh  k tanh"),
    ("alt", "l log2 e exp r round f floor"),
    ("alt", "n nPr  m min  x max  b gcd  8 ∞"),
    ("alt", "v lcm  a atan2 i int  o rand"),
    ("fn", "; . , / arrows  ` esc  1-6 F1-F6"),
    ("fn", "BS del  - home  = end  [ ] page"),
)


def lookup(key):
    """Return the math token for a Key (with OPT/ALT), or None."""
    from cardgcalc.hal import OPT as M_OPT, ALT as M_ALT

    if key.mods & M_OPT:
        return OPT.get(key.base)
    if key.mods & M_ALT:
        return ALT.get(key.base)
    return None
