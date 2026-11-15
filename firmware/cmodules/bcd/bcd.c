// bcd: 15-digit decimal floating point for the card-gcalc calculator apps.
//
// A value is (-1)^neg * c * 10^e with the coefficient c normalised to exactly
// 15 decimal digits (1e14 <= c < 1e15) or zero, and the leading-digit
// exponent limited to -99..99 (overflow raises OverflowError, underflow gives
// 0).  This is the number model of BCD calculators: every result is the
// exact decimal result rounded half-up to 15 significant digits, so 0.1+0.2
// is exactly 0.3.  The coefficient is held as a binary integer (like IEEE
// decimal BID) rather than packed nibbles; the arithmetic is identical.
//
// Internally functions work on an 18-digit "wide" number (w_t) and round
// once at the end.  Elementary functions (sqrt, exp, ln, trig ...) are
// computed in decimal with 3 guard digits.
//
// Python API (module bcd):
//   D(x)                 from str / int / float / D
//   + - * / // % **, comparisons with int / float / D on either side,
//   abs(), -x, int(x), hash(), bool(), str()
//   sqrt cbrt root(x,n) exp ln log10 pow10
//   sin cos tan asin acos atan atan2(y,x)   (optional unit: 0 rad, 1 deg, 2 grad)
//   sinh cosh tanh asinh acosh atanh
//   floor ceil trunc frac rnd(x, n) (n decimals) rsig(x, n) (n sig. digits)
//   parts(x) -> (neg, coef, exp)   make(neg, coef, exp)   tof(x) -> float
//   isint(x)   pi   e

#include <math.h>
#include <string.h>
#include "py/runtime.h"
#include "py/objint.h"
#include "py/smallint.h"
#include "py/parsenum.h"
#include "py/formatfloat.h"

#define DIGITS 15
#define EXP_MAX 99
#define EXP_MIN (-99)

static const uint64_t POW10[20] = {
    1ULL, 10ULL, 100ULL, 1000ULL, 10000ULL, 100000ULL, 1000000ULL, 10000000ULL,
    100000000ULL, 1000000000ULL, 10000000000ULL, 100000000000ULL, 1000000000000ULL,
    10000000000000ULL, 100000000000000ULL, 1000000000000000ULL, 10000000000000000ULL,
    100000000000000000ULL, 1000000000000000000ULL, 10000000000000000000ULL,
};
#define P14 POW10[14]
#define P15 POW10[15]
#define P17 POW10[17]
#define P18 POW10[18]
#define E9 POW10[9]

// ---------------------------------------------------------------------------
// Wide numbers: c == 0 or 1e17 <= c < 1e18, value = c * 10^e
// ---------------------------------------------------------------------------
typedef struct {
    uint64_t c;
    int32_t e;
    bool neg;
} w_t;

static const w_t W0 = {0, 0, false};

static void w_norm(w_t *x) {
    if (x->c == 0) {
        x->e = 0;
        x->neg = false;
        return;
    }
    while (x->c >= P18) {
        x->c /= 10; // truncation (floor of the magnitude)
        x->e++;
    }
    while (x->c < P17) {
        x->c *= 10;
        x->e--;
    }
}

static w_t w_make(bool neg, uint64_t c, int32_t e) {
    w_t x = {c, e, neg};
    w_norm(&x);
    return x;
}

static w_t w_int(int64_t v) {
    return w_make(v < 0, v < 0 ? (uint64_t)(-v) : (uint64_t)v, 0);
}

static w_t w_neg(w_t a) {
    if (a.c) {
        a.neg = !a.neg;
    }
    return a;
}

static w_t w_abs(w_t a) {
    a.neg = false;
    return a;
}

// compare magnitudes: -1, 0, 1
static int w_cmpabs(w_t a, w_t b) {
    if (a.c == 0 || b.c == 0) {
        return (a.c != 0) - (b.c != 0);
    }
    if (a.e != b.e) {
        return a.e < b.e ? -1 : 1;
    }
    return (a.c > b.c) - (a.c < b.c);
}

static int w_cmp(w_t a, w_t b) {
    int sa = a.c == 0 ? 0 : (a.neg ? -1 : 1);
    int sb = b.c == 0 ? 0 : (b.neg ? -1 : 1);
    if (sa != sb) {
        return sa < sb ? -1 : 1;
    }
    int m = w_cmpabs(a, b);
    return sa < 0 ? -m : m;
}

// a + b, magnitude truncated to 18 digits.  When the smaller operand loses
// digits in an effective subtraction one more unit is subtracted so that the
// result is still the floor of the exact magnitude (needed for correct
// half-up rounding afterwards).
static w_t w_add(w_t a, w_t b) {
    if (b.c == 0) {
        return a;
    }
    if (a.c == 0) {
        return b;
    }
    if (w_cmpabs(a, b) < 0) {
        w_t t = a;
        a = b;
        b = t;
    }
    int d = a.e - b.e;
    uint64_t bc = b.c;
    bool sticky = false;
    if (d >= 19) {
        bc = 0;
        sticky = true;
    } else if (d > 0) {
        sticky = (bc % POW10[d]) != 0;
        bc /= POW10[d];
    }
    w_t r;
    r.neg = a.neg;
    r.e = a.e;
    if (a.neg == b.neg) {
        r.c = a.c + bc;
    } else {
        r.c = a.c - bc - (sticky ? 1 : 0);
    }
    w_norm(&r);
    return r;
}

static w_t w_sub(w_t a, w_t b) {
    return w_add(a, w_neg(b));
}

static w_t w_mul(w_t a, w_t b) {
    w_t r = W0;
    if (a.c == 0 || b.c == 0) {
        return r;
    }
    uint64_t a1 = a.c / E9, a0 = a.c % E9, b1 = b.c / E9, b0 = b.c % E9;
    uint64_t t0 = a0 * b0;
    uint64_t t1 = a1 * b0 + a0 * b1 + t0 / E9;
    uint64_t t2 = a1 * b1 + t1 / E9;
    uint64_t l1 = t1 % E9;
    // product = t2 * 1e18 + l1 * 1e9 + (t0 % 1e9), t2 in [1e16, 1e18)
    r.neg = a.neg != b.neg;
    if (t2 >= P17) {
        r.c = t2;
        r.e = a.e + b.e + 18;
    } else {
        r.c = t2 * 10 + l1 / 100000000ULL;
        r.e = a.e + b.e + 17;
    }
    return r;
}

static w_t w_div(w_t a, w_t b) {
    if (b.c == 0) {
        mp_raise_msg(&mp_type_ZeroDivisionError, MP_ERROR_TEXT("divide by zero"));
    }
    w_t r = W0;
    if (a.c == 0) {
        return r;
    }
    uint64_t rem = a.c, q = 0;
    int32_t e = a.e - b.e;
    if (rem < b.c) {
        rem *= 10;
        e--;
    }
    for (int i = 0; i < 18; i++) {
        uint64_t d = rem / b.c;
        rem -= d * b.c;
        q = q * 10 + d;
        rem *= 10;
    }
    r.c = q;
    r.e = e - 17;
    r.neg = a.neg != b.neg;
    return r;
}

static w_t w_muli(w_t a, int64_t n) {
    return w_mul(a, w_int(n));
}

static w_t w_divi(w_t a, int64_t n) {
    return w_div(a, w_int(n));
}

static bool w_isint(w_t a) {
    if (a.c == 0 || a.e >= 0) {
        return true;
    }
    if (a.e <= -18) {
        return false;
    }
    return a.c % POW10[-a.e] == 0;
}

// truncate towards zero
static w_t w_trunc(w_t a) {
    if (a.c == 0 || a.e >= 0) {
        return a;
    }
    if (a.e <= -18) {
        return W0;
    }
    a.c = a.c / POW10[-a.e] * POW10[-a.e];
    w_norm(&a);
    return a;
}

static w_t w_floor(w_t a) {
    w_t t = w_trunc(a);
    if (a.neg && w_cmp(t, a) != 0) {
        t = w_sub(t, w_int(1));
    }
    return t;
}

// integer value of an integral wide number that fits in int64
static int64_t w_toi64(w_t a) {
    a = w_trunc(a);
    if (a.c == 0) {
        return 0;
    }
    uint64_t v = a.c;
    int e = a.e;
    while (e < 0) {
        v /= 10;
        e++;
    }
    while (e > 0) {
        v *= 10;
        e--;
    }
    return a.neg ? -(int64_t)v : (int64_t)v;
}

// round half away from zero to the nearest integer
static w_t w_round(w_t a) {
    w_t h = w_make(a.neg, 5, -1);
    return w_trunc(w_add(a, h));
}

// parse a decimal string ([+-]digits[.digits][e[+-]digits]); keeps 18 digits
static bool w_parse(const char *s, size_t len, w_t *out) {
    size_t i = 0;
    while (i < len && s[i] == ' ') {
        i++;
    }
    bool neg = false;
    if (i < len && (s[i] == '+' || s[i] == '-')) {
        neg = s[i] == '-';
        i++;
    }
    uint64_t c = 0;
    int nd = 0, e = 0;
    bool any = false, dot = false;
    for (; i < len; i++) {
        char ch = s[i];
        if (ch >= '0' && ch <= '9') {
            any = true;
            if (c == 0 && ch == '0') {
                if (dot) {
                    e--;
                }
                continue;
            }
            if (nd < 18) {
                c = c * 10 + (ch - '0');
                nd++;
                if (dot) {
                    e--;
                }
            } else if (!dot) {
                e++;
            }
        } else if (ch == '.' && !dot) {
            dot = true;
        } else {
            break;
        }
    }
    if (!any) {
        return false;
    }
    if (i < len && (s[i] == 'e' || s[i] == 'E')) {
        i++;
        bool eneg = false;
        if (i < len && (s[i] == '+' || s[i] == '-')) {
            eneg = s[i] == '-';
            i++;
        }
        int x = 0;
        bool ed = false;
        while (i < len && s[i] >= '0' && s[i] <= '9') {
            if (x < 100000) {
                x = x * 10 + (s[i] - '0');
            }
            i++;
            ed = true;
        }
        if (!ed) {
            return false;
        }
        e += eneg ? -x : x;
    }
    while (i < len && s[i] == ' ') {
        i++;
    }
    if (i != len) {
        return false;
    }
    *out = w_make(neg, c, e);
    return true;
}

// ---------------------------------------------------------------------------
// Python object
// ---------------------------------------------------------------------------
typedef struct {
    mp_obj_base_t base;
    uint64_t c; // 0 or [1e14, 1e15)
    int16_t e;
    bool neg;
} bcd_obj_t;

const mp_obj_type_t bcd_type;

static w_t d_to_w(const bcd_obj_t *d) {
    w_t w = {d->c * 1000, d->e - 3, d->neg};
    if (d->c == 0) {
        w = W0;
    }
    return w;
}

// round a wide number half-up to 15 digits (range checked)
static bool w_round15(w_t x, uint64_t *c, int32_t *e) {
    w_norm(&x);
    if (x.c == 0) {
        *c = 0;
        *e = 0;
        return true;
    }
    uint64_t q = x.c / 1000;
    if (x.c % 1000 >= 500) {
        q++;
    }
    int32_t ee = x.e + 3;
    if (q == P15) {
        q = P14;
        ee++;
    }
    if (ee + 14 > EXP_MAX) {
        mp_raise_msg(&mp_type_OverflowError, MP_ERROR_TEXT("overflow"));
    }
    if (ee + 14 < EXP_MIN) {
        *c = 0;
        *e = 0;
        return true;
    }
    *c = q;
    *e = ee;
    return true;
}

static mp_obj_t d_new(w_t x) {
    uint64_t c;
    int32_t e;
    w_round15(x, &c, &e);
    bcd_obj_t *o = mp_obj_malloc(bcd_obj_t, &bcd_type);
    o->c = c;
    o->e = (int16_t)e;
    o->neg = c != 0 && x.neg;
    return MP_OBJ_FROM_PTR(o);
}

// wide value rounded to 15 digits (as the stored value would be)
static w_t w_15(w_t x) {
    uint64_t c;
    int32_t e;
    w_round15(x, &c, &e);
    return w_make(x.neg && c != 0, c, e);
}

static bool float_to_w(mp_float_t f, w_t *out) {
    if (isinf(f) || isnan(f)) {
        return false;
    }
    char buf[40];
    int n = mp_format_float(f, buf, sizeof(buf), 'e', 16, '\0');
    if (n <= 0 || !w_parse(buf, n, out)) {
        return false;
    }
    *out = w_15(*out);
    return true;
}

static bool int_to_w(mp_obj_t o, w_t *out) {
    if (mp_obj_is_small_int(o)) {
        *out = w_15(w_int(MP_OBJ_SMALL_INT_VALUE(o)));
        return true;
    }
    // big int: go through its decimal string
    vstr_t vstr;
    mp_print_t print;
    vstr_init_print(&vstr, 24, &print);
    mp_obj_print_helper(&print, o, PRINT_STR);
    bool ok = w_parse(vstr.buf, vstr.len, out);
    vstr_clear(&vstr);
    if (ok) {
        *out = w_15(*out);
    }
    return ok;
}

// Convert a Python number to a wide number.  Returns false for unsupported
// types (and for inf / nan floats).
static bool obj_to_w(mp_obj_t o, w_t *out) {
    if (mp_obj_is_type(o, &bcd_type)) {
        *out = d_to_w(MP_OBJ_TO_PTR(o));
        return true;
    }
    if (o == mp_const_false) {
        *out = W0;
        return true;
    }
    if (o == mp_const_true) {
        *out = w_int(1);
        return true;
    }
    if (mp_obj_is_int(o)) {
        return int_to_w(o, out);
    }
    if (mp_obj_is_float(o)) {
        return float_to_w(mp_obj_float_get(o), out);
    }
    return false;
}

static w_t arg_w(mp_obj_t o) {
    w_t w;
    if (mp_obj_is_str(o)) {
        size_t l;
        const char *s = mp_obj_str_get_data(o, &l);
        if (w_parse(s, l, &w)) {
            return w_15(w);
        }
        mp_raise_ValueError(MP_ERROR_TEXT("invalid number"));
    }
    if (!obj_to_w(o, &w)) {
        if (mp_obj_is_float(o)) {
            mp_raise_msg(&mp_type_OverflowError, MP_ERROR_TEXT("overflow"));
        }
        mp_raise_TypeError(MP_ERROR_TEXT("number required"));
    }
    return w;
}

// format the 15-digit value into buf (Python float repr style)
static size_t d_format(const bcd_obj_t *d, char *buf) {
    char dig[16];
    size_t n = 0;
    if (d->c == 0) {
        buf[0] = '0';
        buf[1] = 0;
        return 1;
    }
    uint64_t c = d->c;
    for (int i = 14; i >= 0; i--) {
        dig[i] = '0' + c % 10;
        c /= 10;
    }
    int nd = 15;
    while (nd > 1 && dig[nd - 1] == '0') {
        nd--;
    }
    int x = d->e + 14; // exponent of the leading digit
    if (d->neg) {
        buf[n++] = '-';
    }
    if (x >= -5 && x < 15) {
        if (x >= 0) {
            for (int i = 0; i <= x; i++) {
                buf[n++] = i < nd ? dig[i] : '0';
            }
            if (nd > x + 1) {
                buf[n++] = '.';
                for (int i = x + 1; i < nd; i++) {
                    buf[n++] = dig[i];
                }
            }
        } else {
            buf[n++] = '0';
            buf[n++] = '.';
            for (int i = 0; i < -x - 1; i++) {
                buf[n++] = '0';
            }
            for (int i = 0; i < nd; i++) {
                buf[n++] = dig[i];
            }
        }
    } else {
        buf[n++] = dig[0];
        if (nd > 1) {
            buf[n++] = '.';
            for (int i = 1; i < nd; i++) {
                buf[n++] = dig[i];
            }
        }
        buf[n++] = 'e';
        buf[n++] = x < 0 ? '-' : '+';
        int ax = x < 0 ? -x : x;
        if (ax >= 100) {
            buf[n++] = '0' + ax / 100;
        }
        buf[n++] = '0' + ax / 10 % 10;
        buf[n++] = '0' + ax % 10;
    }
    buf[n] = 0;
    return n;
}

static void bcd_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    char buf[32];
    d_format(MP_OBJ_TO_PTR(self_in), buf);
    mp_print_str(print, buf);
}

static mp_obj_t bcd_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    (void)type;
    mp_arg_check_num(n_args, n_kw, 0, 1, false);
    if (n_args == 0) {
        return d_new(W0);
    }
    if (mp_obj_is_type(args[0], &bcd_type)) {
        return args[0];
    }
    return d_new(arg_w(args[0]));
}

// Python int from an integral wide value (any size)
static mp_obj_t w_to_pyint(w_t a) {
    a = w_trunc(a);
    if (a.c == 0) {
        return MP_OBJ_NEW_SMALL_INT(0);
    }
    if (a.e <= 0) {
        return mp_obj_new_int_from_ll(w_toi64(a));
    }
    char buf[140];
    size_t n = 0;
    if (a.neg) {
        buf[n++] = '-';
    }
    uint64_t c = a.c;
    char dig[18];
    for (int i = 17; i >= 0; i--) {
        dig[i] = '0' + c % 10;
        c /= 10;
    }
    for (int i = 0; i < 18; i++) {
        buf[n++] = dig[i];
    }
    for (int i = 0; i < a.e && n < sizeof(buf); i++) {
        buf[n++] = '0';
    }
    return mp_parse_num_integer(buf, n, 10, NULL);
}

static mp_obj_t bcd_unary_op(mp_unary_op_t op, mp_obj_t o_in) {
    bcd_obj_t *o = MP_OBJ_TO_PTR(o_in);
    switch (op) {
        case MP_UNARY_OP_BOOL:
            return mp_obj_new_bool(o->c != 0);
        case MP_UNARY_OP_POSITIVE:
            return o_in;
        case MP_UNARY_OP_NEGATIVE:
            return d_new(w_neg(d_to_w(o)));
        case MP_UNARY_OP_ABS:
            return o->neg ? d_new(w_abs(d_to_w(o))) : o_in;
        case MP_UNARY_OP_INT_MAYBE:
            return w_to_pyint(d_to_w(o));
        case MP_UNARY_OP_HASH: {
            w_t w = d_to_w(o);
            if (w_isint(w) && w.e <= 0) {
                int64_t v = w_toi64(w);
                if (v >= MP_SMALL_INT_MIN && v <= MP_SMALL_INT_MAX) {
                    return MP_OBJ_NEW_SMALL_INT(v);
                }
            }
            mp_int_t h = (mp_int_t)(o->c ^ (o->c >> 31)) ^ ((mp_int_t)o->e << 20) ^ o->neg;
            return MP_OBJ_NEW_SMALL_INT(h & (MP_SMALL_INT_MAX >> 1));
        }
        default:
            return MP_OBJ_NULL;
    }
}

// ---- power -----------------------------------------------------------------
static w_t w_exp(w_t x);
static w_t w_ln(w_t x);
static w_t w_sqrt(w_t x);

// x^n for integer n by repeated squaring
static w_t w_powi(w_t x, int64_t n) {
    bool inv = n < 0;
    uint64_t m = inv ? (uint64_t)0 - (uint64_t)n : (uint64_t)n;
    w_t r = w_int(1);
    w_t b = x;
    while (m) {
        if (m & 1) {
            r = w_mul(r, b);
        }
        m >>= 1;
        if (m) {
            b = w_mul(b, b);
        }
        // far outside the range (b is still to be multiplied in while m != 0)
        bool big = (r.c && r.e > 400) || (m && b.e > 400);
        bool small = (r.c && r.e < -400) || (m && b.c && b.e < -400);
        if (big) {
            if (inv) {
                return W0;
            }
            mp_raise_msg(&mp_type_OverflowError, MP_ERROR_TEXT("overflow"));
        }
        if (small) {
            if (inv) {
                mp_raise_msg(&mp_type_OverflowError, MP_ERROR_TEXT("overflow"));
            }
            return W0;
        }
    }
    if (inv) {
        r = w_div(w_int(1), r);
    }
    return r;
}

static w_t w_pow(w_t x, w_t y) {
    if (y.c == 0) {
        return w_int(1);
    }
    if (x.c == 0) {
        if (y.neg) {
            mp_raise_msg(&mp_type_ZeroDivisionError, MP_ERROR_TEXT("divide by zero"));
        }
        return W0;
    }
    if (w_isint(y) && w_cmpabs(y, w_int(1000000000LL)) <= 0) {
        return w_powi(x, w_toi64(y));
    }
    // half-integer exponents through sqrt (exact for perfect squares)
    w_t y2 = w_muli(y, 2);
    if (w_isint(y2) && !x.neg && w_cmpabs(y2, w_int(1000000000LL)) <= 0) {
        return w_powi(w_sqrt(x), w_toi64(y2));
    }
    if (x.neg) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    return w_exp(w_mul(y, w_ln(x)));
}

// exact remainder with the sign of b (Python semantics); a, b 15-digit values
static w_t w_mod(w_t a, w_t b) {
    if (b.c == 0) {
        mp_raise_msg(&mp_type_ZeroDivisionError, MP_ERROR_TEXT("divide by zero"));
    }
    if (a.c == 0) {
        return W0;
    }
    // back to 15-digit coefficients
    uint64_t ca = a.c / 1000, cb = b.c / 1000;
    int32_t ea = a.e + 3, eb = b.e + 3;
    while (ca % 10 == 0) {
        ca /= 10;
        ea++;
    }
    while (cb % 10 == 0) {
        cb /= 10;
        eb++;
    }
    w_t r;
    if (ea >= eb) {
        uint64_t m = ca % cb;
        for (int32_t k = 0; k < ea - eb; k++) {
            m = (m * 10) % cb;
        }
        r = w_make(false, m, eb);
    } else {
        // divisor cb * 10^k (k > 0); if it exceeds ca the remainder is ca
        int32_t k = eb - ea;
        uint64_t m = ca;
        if (k < 16 && cb <= P18 / POW10[k]) {
            m = ca % (cb * POW10[k]);
        }
        r = w_make(false, m, ea);
    }
    if (r.c != 0 && a.neg != b.neg) {
        r = w_sub(w_abs(b), r);
    }
    if (r.c != 0) {
        r.neg = b.neg;
    }
    return r;
}

static mp_obj_t bcd_binary_op(mp_binary_op_t op, mp_obj_t lhs_in, mp_obj_t rhs_in) {
    // comparisons with +-inf floats
    w_t a, b;
    bool rev = false;
    if (op >= MP_BINARY_OP_REVERSE_OR && op <= MP_BINARY_OP_REVERSE_POWER) {
        rev = true;
        op -= MP_BINARY_OP_REVERSE_OR - MP_BINARY_OP_OR;
    }
    if (!obj_to_w(lhs_in, &a)) {
        return MP_OBJ_NULL;
    }
    if (!obj_to_w(rhs_in, &b)) {
        if (mp_obj_is_float(rhs_in) && op <= MP_BINARY_OP_NOT_EQUAL) {
            mp_float_t f = mp_obj_float_get(rhs_in);
            if (isinf(f)) {
                switch (op) {
                    case MP_BINARY_OP_LESS:
                    case MP_BINARY_OP_LESS_EQUAL:
                        return mp_obj_new_bool(f > 0);
                    case MP_BINARY_OP_MORE:
                    case MP_BINARY_OP_MORE_EQUAL:
                        return mp_obj_new_bool(f < 0);
                    case MP_BINARY_OP_EQUAL:
                        return mp_const_false;
                    case MP_BINARY_OP_NOT_EQUAL:
                        return mp_const_true;
                    default:
                        break;
                }
            }
            if (op == MP_BINARY_OP_EQUAL) {
                return mp_const_false;
            }
            if (op == MP_BINARY_OP_NOT_EQUAL) {
                return mp_const_true;
            }
        }
        return MP_OBJ_NULL;
    }
    if (rev) {
        w_t t = a;
        a = b;
        b = t;
    }
    switch (op) {
        case MP_BINARY_OP_ADD:
        case MP_BINARY_OP_INPLACE_ADD:
            return d_new(w_add(a, b));
        case MP_BINARY_OP_SUBTRACT:
        case MP_BINARY_OP_INPLACE_SUBTRACT:
            return d_new(w_sub(a, b));
        case MP_BINARY_OP_MULTIPLY:
        case MP_BINARY_OP_INPLACE_MULTIPLY:
            return d_new(w_mul(a, b));
        case MP_BINARY_OP_TRUE_DIVIDE:
        case MP_BINARY_OP_INPLACE_TRUE_DIVIDE:
            return d_new(w_div(a, b));
        case MP_BINARY_OP_FLOOR_DIVIDE:
        case MP_BINARY_OP_INPLACE_FLOOR_DIVIDE: {
            w_t r = w_mod(a, b);
            return d_new(w_floor(w_div(w_sub(a, r), b)));
        }
        case MP_BINARY_OP_MODULO:
        case MP_BINARY_OP_INPLACE_MODULO:
            return d_new(w_mod(a, b));
        case MP_BINARY_OP_POWER:
        case MP_BINARY_OP_INPLACE_POWER:
            return d_new(w_pow(a, b));
        case MP_BINARY_OP_LESS:
            return mp_obj_new_bool(w_cmp(a, b) < 0);
        case MP_BINARY_OP_MORE:
            return mp_obj_new_bool(w_cmp(a, b) > 0);
        case MP_BINARY_OP_LESS_EQUAL:
            return mp_obj_new_bool(w_cmp(a, b) <= 0);
        case MP_BINARY_OP_MORE_EQUAL:
            return mp_obj_new_bool(w_cmp(a, b) >= 0);
        case MP_BINARY_OP_EQUAL:
            return mp_obj_new_bool(w_cmp(a, b) == 0);
        case MP_BINARY_OP_NOT_EQUAL:
            return mp_obj_new_bool(w_cmp(a, b) != 0);
        default:
            return MP_OBJ_NULL;
    }
}

MP_DEFINE_CONST_OBJ_TYPE(
    bcd_type,
    MP_QSTR_D,
    MP_TYPE_FLAG_EQ_CHECKS_OTHER_TYPE,
    make_new, bcd_make_new,
    print, bcd_print,
    unary_op, bcd_unary_op,
    binary_op, bcd_binary_op
    );

// ---------------------------------------------------------------------------
// Elementary functions (wide precision)
// ---------------------------------------------------------------------------
// constants, 18 significant digits
#define WC(neg, c, e) ((w_t) {c, e, neg})
static const w_t PI = WC(false, 314159265358979324ULL, -17);
static const w_t PI_2 = WC(false, 157079632679489662ULL, -17);
static const w_t LN10 = WC(false, 230258509299404568ULL, -17);
static const w_t LN2 = WC(false, 693147180559945309ULL, -18);
static const w_t RAD_PER_DEG = WC(false, 174532925199432958ULL, -19);
static const w_t DEG_PER_RAD = WC(false, 572957795130823209ULL, -16);
static const w_t RAD_PER_GRAD = WC(false, 157079632679489662ULL, -19);
static const w_t GRAD_PER_RAD = WC(false, 636619772367581343ULL, -16);
// pi/2 in 8-digit pieces for exact argument reduction (Cody-Waite)
static const uint64_t PI2_PART[6] = {15707963ULL, 26794896ULL, 61923132ULL, 16916397ULL, 51442098ULL, 58469968ULL};
// ln(10) = L1 + L2 with k*L1 exact for |k| < 1000
static const w_t LN10_1 = WC(false, 230258509299404000ULL, -17);
static const w_t LN10_2 = WC(false, 568401799145468436ULL, -32);

static const w_t W1 = WC(false, 100000000000000000ULL, -17);

static bool w_lt_tiny(w_t t, w_t ref, int digits) {
    // |t| < |ref| * 10^-digits ?
    if (t.c == 0) {
        return true;
    }
    if (ref.c == 0) {
        return false;
    }
    return t.e + 17 < ref.e + 17 - digits;
}

static w_t w_sqrt(w_t x) {
    if (x.c == 0) {
        return W0;
    }
    if (x.neg) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    // initial guess from double
    int32_t e = x.e + 17;
    double m = (double)x.c / 1e17;
    if (e & 1) {
        m *= 10;
        e--;
    }
    double g = sqrt(m);
    w_t y = w_make(false, (uint64_t)(g * 1e16), e / 2 - 16);
    for (int i = 0; i < 3; i++) {
        y = w_divi(w_add(y, w_div(x, y)), 2);
    }
    // make perfect squares exact
    w_t y15 = w_15(y);
    if (w_cmp(w_mul(y15, y15), x) == 0) {
        return y15;
    }
    return y;
}

static w_t w_rootn(w_t x, int64_t n) {
    // real n-th root (n >= 2); negative x only for odd n
    if (x.c == 0) {
        return W0;
    }
    bool neg = x.neg;
    if (neg && n % 2 == 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    x.neg = false;
    double lx = log10((double)x.c) + x.e;
    double lg = lx / (double)n;
    double fl = floor(lg);
    w_t y = w_make(false, (uint64_t)(pow(10.0, lg - fl) * 1e16), (int32_t)fl - 16);
    w_t nn = w_int(n);
    for (int i = 0; i < 4; i++) {
        // y = ((n-1) y + x / y^(n-1)) / n
        w_t p = w_powi(y, n - 1);
        y = w_div(w_add(w_muli(y, n - 1), w_div(x, p)), nn);
    }
    w_t y15 = w_15(y);
    if (w_cmp(w_powi(y15, n), x) == 0) {
        y = y15;
    }
    y.neg = neg;
    return y;
}

// exp(r) for |r| <= ~1.2, r >= 0
static w_t w_exp_series(w_t r) {
    w_t s = W1, t = W1;
    for (int k = 1; k < 40; k++) {
        t = w_divi(w_mul(t, r), k);
        if (t.c == 0 || w_lt_tiny(t, s, 19)) {
            break;
        }
        s = w_add(s, t);
    }
    return s;
}

static w_t w_exp(w_t x) {
    if (x.c == 0) {
        return W1;
    }
    // range: e^x < 1e100  <=>  x < 230.2585...
    if (w_cmp(x, w_int(231)) > 0) {
        mp_raise_msg(&mp_type_OverflowError, MP_ERROR_TEXT("overflow"));
    }
    if (w_cmp(x, w_int(-232)) < 0) {
        return W0;
    }
    int64_t k = w_toi64(w_round(w_div(x, LN10)));
    w_t r = w_sub(w_sub(x, w_muli(LN10_1, k)), w_muli(LN10_2, k));
    bool neg = r.neg;
    r.neg = false;
    w_t s = w_exp_series(r);
    if (neg) {
        s = w_div(W1, s);
    }
    s.e += (int32_t)k;
    return s;
}

static w_t w_ln_core(w_t m) {
    // ln(m) for m in [0.75, 1.5]: 2 atanh(z), z = (m-1)/(m+1)
    w_t z = w_div(w_sub(m, W1), w_add(m, W1));
    if (z.c == 0) {
        return W0;
    }
    w_t z2 = w_mul(z, z);
    w_t s = z, t = z;
    for (int k = 3; k < 200; k += 2) {
        t = w_mul(t, z2);
        w_t term = w_divi(t, k);
        if (term.c == 0 || w_lt_tiny(term, s, 19)) {
            break;
        }
        s = w_add(s, term);
    }
    return w_muli(s, 2);
}

// x = 10^E * 2^j * m with m in [0.75, 1.5]
static void w_ln_split(w_t x, int32_t *E, int *j, w_t *m) {
    *E = x.e + 17;
    w_t mm = x;
    mm.e = -17; // leading digit form, [1, 10)
    static const w_t SQRT10 = WC(false, 316227766016837933ULL, -17);
    if (w_cmp(mm, SQRT10) >= 0) {
        mm.e -= 1;
        (*E)++;
    }
    *j = 0;
    w_t half = WC(false, 500000000000000000ULL, -18);
    w_t two = w_int(2);
    w_t hi = WC(false, 150000000000000000ULL, -17);
    w_t lo = WC(false, 750000000000000000ULL, -18);
    while (w_cmp(mm, hi) > 0) {
        mm = w_mul(mm, half);
        (*j)++;
    }
    while (w_cmp(mm, lo) < 0) {
        mm = w_mul(mm, two);
        (*j)--;
    }
    *m = mm;
}

static w_t w_ln(w_t x) {
    if (x.c == 0 || x.neg) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    int32_t E;
    int j;
    w_t m;
    w_ln_split(x, &E, &j, &m);
    w_t r = w_ln_core(m);
    if (j) {
        r = w_add(r, w_muli(LN2, j));
    }
    if (E) {
        r = w_add(r, w_muli(LN10, E));
    }
    return r;
}

static w_t w_log10(w_t x) {
    if (x.c == 0 || x.neg) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    int32_t E;
    int j;
    w_t m;
    w_ln_split(x, &E, &j, &m);
    w_t r = w_ln_core(m);
    if (j) {
        r = w_add(r, w_muli(LN2, j));
    }
    r = w_div(r, LN10);
    return w_add(w_int(E), r);
}

// sin and cos of r, |r| <= pi/4 (+ a little)
static void w_sincos_core(w_t r, w_t *s, w_t *c) {
    w_t r2 = w_mul(r, r);
    w_t ss = r, t = r;
    for (int k = 2; k < 60; k += 2) {
        t = w_neg(w_divi(w_mul(t, r2), (int64_t)k * (k + 1)));
        if (t.c == 0 || w_lt_tiny(t, ss, 19)) {
            break;
        }
        ss = w_add(ss, t);
    }
    w_t cc = W1;
    t = W1;
    for (int k = 1; k < 60; k += 2) {
        t = w_neg(w_divi(w_mul(t, r2), (int64_t)k * (k + 1)));
        if (t.c == 0 || w_lt_tiny(t, cc, 19)) {
            break;
        }
        cc = w_add(cc, t);
    }
    *s = r.c ? ss : W0;
    *c = cc;
}

// Reduce x (in the given unit) to a quadrant q (0..3) and a remainder r in
// radians with |r| <= pi/4 (approximately).  exact: r is exactly 0.
static void w_reduce(w_t x, int unit, int *q, w_t *r) {
    if (unit != 0) {
        // degrees / grads: exact decimal reduction
        w_t quarter = w_int(unit == 1 ? 90 : 100);
        w_t full = w_int(unit == 1 ? 360 : 400);
        w_t xr = w_mod(w_15(x), full); // [0, full)
        int k = (int)w_toi64(w_round(w_div(xr, quarter)));
        w_t t = w_sub(xr, w_muli(quarter, k)); // exact, |t| <= quarter/2
        *q = k & 3;
        *r = t.c == 0 ? W0 : w_mul(t, unit == 1 ? RAD_PER_DEG : RAD_PER_GRAD);
        return;
    }
    if (w_cmpabs(x, w_int(10000000000LL)) > 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    int64_t k = w_toi64(w_round(w_div(x, PI_2)));
    w_t t = x;
    int32_t pe = -7;
    for (int i = 0; i < 6; i++) {
        t = w_sub(t, w_mul(w_int(k), w_make(false, PI2_PART[i], pe)));
        pe -= 8;
    }
    // x is a 15-digit value: a remainder below half a unit in its last place
    // (plus the error of k times the 15-digit pi/2, as in 2*pi) means x is
    // the stored form of an exact multiple of pi/2.
    if (k != 0 && t.c != 0) {
        w_t thr = w_add(w_make(false, 5, x.e + 17 - 15), w_muli(w_make(false, 17, -16), k < 0 ? -k : k));
        if (w_cmpabs(t, thr) < 0) {
            t = W0;
        }
    }
    *q = (int)(k & 3);
    *r = t;
}

static void w_sincos(w_t x, int unit, w_t *s, w_t *c, bool *c_exact0, bool *s_exact0) {
    int q;
    w_t r;
    w_reduce(x, unit, &q, &r);
    w_t ss, cc;
    w_sincos_core(r, &ss, &cc);
    bool z = r.c == 0;
    switch (q) {
        case 0:
            *s = ss;
            *c = cc;
            *s_exact0 = z;
            *c_exact0 = false;
            break;
        case 1:
            *s = cc;
            *c = w_neg(ss);
            *s_exact0 = false;
            *c_exact0 = z;
            break;
        case 2:
            *s = w_neg(ss);
            *c = w_neg(cc);
            *s_exact0 = z;
            *c_exact0 = false;
            break;
        default:
            *s = w_neg(cc);
            *c = ss;
            *s_exact0 = false;
            *c_exact0 = z;
            break;
    }
}

// atan for x >= 0
static w_t w_atan_pos(w_t x) {
    bool inv = w_cmp(x, W1) > 0;
    if (inv) {
        x = w_div(W1, x);
    }
    // two argument halvings: atan(x) = 2 atan(x / (1 + sqrt(1 + x^2)))
    for (int i = 0; i < 2; i++) {
        x = w_div(x, w_add(W1, w_sqrt(w_add(W1, w_mul(x, x)))));
    }
    w_t x2 = w_mul(x, x);
    w_t s = x, t = x;
    for (int k = 3; k < 200; k += 2) {
        t = w_neg(w_mul(t, x2));
        w_t term = w_divi(t, k);
        if (term.c == 0 || w_lt_tiny(term, s, 19)) {
            break;
        }
        s = w_add(s, term);
    }
    s = w_muli(s, 4);
    if (inv) {
        s = w_sub(PI_2, s);
    }
    return s;
}

static w_t w_atan2(w_t y, w_t x) {
    if (x.c == 0) {
        if (y.c == 0) {
            return W0;
        }
        return y.neg ? w_neg(PI_2) : PI_2;
    }
    w_t a = w_atan_pos(w_abs(w_div(y, x)));
    if (x.neg) {
        a = w_sub(PI, a);
    }
    if (y.neg) {
        a = w_neg(a);
    }
    return a;
}

static w_t w_from_rad(w_t a, int unit) {
    if (unit == 1) {
        return w_mul(a, DEG_PER_RAD);
    }
    if (unit == 2) {
        return w_mul(a, GRAD_PER_RAD);
    }
    return a;
}

// ---------------------------------------------------------------------------
// Module functions
// ---------------------------------------------------------------------------
static int unit_arg(size_t n_args, const mp_obj_t *args, size_t i) {
    return n_args > i ? (int)mp_obj_get_int(args[i]) : 0;
}

static mp_obj_t f_sqrt(mp_obj_t x) {
    return d_new(w_sqrt(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_sqrt_obj, f_sqrt);

static mp_obj_t f_cbrt(mp_obj_t x) {
    return d_new(w_rootn(arg_w(x), 3));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_cbrt_obj, f_cbrt);

static mp_obj_t f_root(mp_obj_t x, mp_obj_t n) {
    mp_int_t k = mp_obj_get_int(n);
    if (k < 1) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    if (k == 1) {
        return d_new(arg_w(x));
    }
    return d_new(w_rootn(arg_w(x), k));
}
static MP_DEFINE_CONST_FUN_OBJ_2(f_root_obj, f_root);

static mp_obj_t f_exp(mp_obj_t x) {
    return d_new(w_exp(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_exp_obj, f_exp);

static mp_obj_t f_ln(mp_obj_t x) {
    return d_new(w_ln(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_ln_obj, f_ln);

static mp_obj_t f_log10(mp_obj_t x) {
    return d_new(w_log10(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_log10_obj, f_log10);

static mp_obj_t f_pow10(mp_obj_t x) {
    w_t w = arg_w(x);
    if (w_isint(w)) {
        if (w_cmp(w, w_int(100)) >= 0) {
            mp_raise_msg(&mp_type_OverflowError, MP_ERROR_TEXT("overflow"));
        }
        if (w_cmp(w, w_int(-120)) < 0) {
            return d_new(W0);
        }
        return d_new(w_make(false, 1, (int32_t)w_toi64(w)));
    }
    return d_new(w_exp(w_mul(w, LN10)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_pow10_obj, f_pow10);

static mp_obj_t f_sin(size_t n_args, const mp_obj_t *args) {
    w_t s, c;
    bool c0, s0;
    w_sincos(arg_w(args[0]), unit_arg(n_args, args, 1), &s, &c, &c0, &s0);
    return d_new(s0 ? W0 : s);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_sin_obj, 1, 2, f_sin);

static mp_obj_t f_cos(size_t n_args, const mp_obj_t *args) {
    w_t s, c;
    bool c0, s0;
    w_sincos(arg_w(args[0]), unit_arg(n_args, args, 1), &s, &c, &c0, &s0);
    return d_new(c0 ? W0 : c);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_cos_obj, 1, 2, f_cos);

static mp_obj_t f_tan(size_t n_args, const mp_obj_t *args) {
    w_t s, c;
    bool c0, s0;
    w_sincos(arg_w(args[0]), unit_arg(n_args, args, 1), &s, &c, &c0, &s0);
    if (c0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    if (s0) {
        return d_new(W0);
    }
    return d_new(w_div(s, c));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_tan_obj, 1, 2, f_tan);

static mp_obj_t f_atan(size_t n_args, const mp_obj_t *args) {
    w_t x = arg_w(args[0]);
    w_t a = w_atan_pos(w_abs(x));
    if (x.neg) {
        a = w_neg(a);
    }
    return d_new(w_from_rad(a, unit_arg(n_args, args, 1)));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_atan_obj, 1, 2, f_atan);

static mp_obj_t f_atan2(size_t n_args, const mp_obj_t *args) {
    w_t a = w_atan2(arg_w(args[0]), arg_w(args[1]));
    return d_new(w_from_rad(a, unit_arg(n_args, args, 2)));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_atan2_obj, 2, 3, f_atan2);

static mp_obj_t f_asin(size_t n_args, const mp_obj_t *args) {
    w_t x = arg_w(args[0]);
    int c = w_cmpabs(x, W1);
    if (c > 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    w_t a;
    if (c == 0) {
        a = PI_2;
    } else {
        // atan(x / sqrt((1-x)(1+x)))
        w_t ax = w_abs(x);
        w_t d = w_sqrt(w_mul(w_sub(W1, ax), w_add(W1, ax)));
        a = w_atan_pos(w_div(ax, d));
    }
    if (x.neg) {
        a = w_neg(a);
    }
    return d_new(w_from_rad(a, unit_arg(n_args, args, 1)));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_asin_obj, 1, 2, f_asin);

static mp_obj_t f_acos(size_t n_args, const mp_obj_t *args) {
    w_t x = arg_w(args[0]);
    int c = w_cmpabs(x, W1);
    if (c > 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    w_t a;
    if (c == 0) {
        a = x.neg ? PI : W0;
    } else {
        // 2 atan(sqrt((1-x)/(1+x)))
        a = w_muli(w_atan_pos(w_sqrt(w_div(w_sub(W1, x), w_add(W1, x)))), 2);
    }
    return d_new(w_from_rad(a, unit_arg(n_args, args, 1)));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_acos_obj, 1, 2, f_acos);

static w_t w_sinh(w_t x) {
    w_t ax = w_abs(x);
    w_t r;
    if (w_cmp(ax, WC(false, 500000000000000000ULL, -18)) < 0) {
        // series
        w_t x2 = w_mul(x, x), t = ax;
        r = ax;
        for (int k = 2; k < 60; k += 2) {
            t = w_divi(w_mul(t, x2), (int64_t)k * (k + 1));
            if (t.c == 0 || w_lt_tiny(t, r, 19)) {
                break;
            }
            r = w_add(r, t);
        }
    } else {
        w_t ex = w_exp(ax);
        r = w_divi(w_sub(ex, w_div(W1, ex)), 2);
    }
    if (x.neg) {
        r = w_neg(r);
    }
    return r;
}

static mp_obj_t f_sinh(mp_obj_t x) {
    return d_new(w_sinh(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_sinh_obj, f_sinh);

static mp_obj_t f_cosh(mp_obj_t x) {
    w_t ex = w_exp(w_abs(arg_w(x)));
    return d_new(w_divi(w_add(ex, w_div(W1, ex)), 2));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_cosh_obj, f_cosh);

static mp_obj_t f_tanh(mp_obj_t x) {
    w_t w = arg_w(x);
    if (w_cmpabs(w, w_int(25)) > 0) {
        return d_new(w_make(w.neg, 1, 0));
    }
    w_t ex = w_exp(w_abs(w));
    w_t c = w_divi(w_add(ex, w_div(W1, ex)), 2);
    return d_new(w_div(w_sinh(w), c));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_tanh_obj, f_tanh);

static mp_obj_t f_asinh(mp_obj_t x) {
    w_t w = arg_w(x), ax = w_abs(w), r;
    if (w_cmp(ax, WC(false, 100000000000000000ULL, -19)) < 0) {
        // x - x^3/6 + 3x^5/40 - 5x^7/112
        w_t x2 = w_mul(ax, ax);
        w_t t3 = w_mul(ax, x2), t5 = w_mul(t3, x2), t7 = w_mul(t5, x2);
        r = w_sub(ax, w_divi(t3, 6));
        r = w_add(r, w_divi(w_muli(t5, 3), 40));
        r = w_sub(r, w_divi(w_muli(t7, 5), 112));
    } else {
        r = w_ln(w_add(ax, w_sqrt(w_add(w_mul(ax, ax), W1))));
    }
    if (w.neg) {
        r = w_neg(r);
    }
    return d_new(r);
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_asinh_obj, f_asinh);

static mp_obj_t f_acosh(mp_obj_t x) {
    w_t w = arg_w(x);
    if (w_cmp(w, W1) < 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    w_t s = w_sqrt(w_mul(w_sub(w, W1), w_add(w, W1)));
    return d_new(w_ln(w_add(w, s)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_acosh_obj, f_acosh);

static mp_obj_t f_atanh(mp_obj_t x) {
    w_t w = arg_w(x), ax = w_abs(w), r;
    if (w_cmp(ax, W1) >= 0) {
        mp_raise_ValueError(MP_ERROR_TEXT("math domain error"));
    }
    if (w_cmp(ax, WC(false, 100000000000000000ULL, -19)) < 0) {
        w_t x2 = w_mul(ax, ax), t = ax;
        r = ax;
        for (int k = 3; k < 40; k += 2) {
            t = w_mul(t, x2);
            w_t term = w_divi(t, k);
            if (term.c == 0 || w_lt_tiny(term, r, 19)) {
                break;
            }
            r = w_add(r, term);
        }
    } else {
        r = w_divi(w_ln(w_div(w_add(W1, ax), w_sub(W1, ax))), 2);
    }
    if (w.neg) {
        r = w_neg(r);
    }
    return d_new(r);
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_atanh_obj, f_atanh);

static mp_obj_t f_floor(mp_obj_t x) {
    return d_new(w_floor(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_floor_obj, f_floor);

static mp_obj_t f_ceil(mp_obj_t x) {
    return d_new(w_neg(w_floor(w_neg(arg_w(x)))));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_ceil_obj, f_ceil);

static mp_obj_t f_trunc(mp_obj_t x) {
    return d_new(w_trunc(arg_w(x)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_trunc_obj, f_trunc);

static mp_obj_t f_frac(mp_obj_t x) {
    w_t w = arg_w(x);
    return d_new(w_sub(w, w_trunc(w)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_frac_obj, f_frac);

// round half away from zero to n decimal places
static mp_obj_t f_rnd(size_t n_args, const mp_obj_t *args) {
    w_t w = arg_w(args[0]);
    mp_int_t n = n_args > 1 ? mp_obj_get_int(args[1]) : 0;
    if (w.c == 0) {
        return d_new(W0);
    }
    w.e += n;
    w = w_round(w);
    w.e -= n;
    return d_new(w);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(f_rnd_obj, 1, 2, f_rnd);

// round half away from zero to n significant digits
static mp_obj_t f_rsig(mp_obj_t x, mp_obj_t n_in) {
    w_t w = arg_w(x);
    mp_int_t n = mp_obj_get_int(n_in);
    if (w.c == 0 || n >= 15) {
        return d_new(w);
    }
    if (n < 1) {
        n = 1;
    }
    int32_t lead = w.e + 17;
    int32_t sh = n - 1 - lead; // scale so that n digits are left of the point
    w.e += sh;
    w = w_round(w);
    w.e -= sh;
    return d_new(w);
}
static MP_DEFINE_CONST_FUN_OBJ_2(f_rsig_obj, f_rsig);

static mp_obj_t f_parts(mp_obj_t x) {
    if (!mp_obj_is_type(x, &bcd_type)) {
        x = d_new(arg_w(x));
    }
    bcd_obj_t *d = MP_OBJ_TO_PTR(x);
    mp_obj_t t[3] = {mp_obj_new_bool(d->neg), mp_obj_new_int_from_ull(d->c), MP_OBJ_NEW_SMALL_INT(d->e)};
    return mp_obj_new_tuple(3, t);
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_parts_obj, f_parts);

// make(neg, coef, exp): coef may be any non-negative Python int
static mp_obj_t f_make(mp_obj_t neg, mp_obj_t coef, mp_obj_t exp) {
    w_t w;
    if (!int_to_w(coef, &w)) {
        mp_raise_TypeError(NULL);
    }
    if (w.c) {
        w.e += mp_obj_get_int(exp);
        w.neg = mp_obj_is_true(neg);
    }
    return d_new(w);
}
static MP_DEFINE_CONST_FUN_OBJ_3(f_make_obj, f_make);

static mp_obj_t f_tof(mp_obj_t x) {
    if (mp_obj_is_float(x)) {
        return x;
    }
    if (!mp_obj_is_type(x, &bcd_type)) {
        return mp_obj_new_float(mp_obj_get_float(x));
    }
    char buf[32];
    size_t n = d_format(MP_OBJ_TO_PTR(x), buf);
    return mp_parse_num_float(buf, n, false, NULL);
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_tof_obj, f_tof);

static mp_obj_t f_isint(mp_obj_t x) {
    w_t w;
    if (!obj_to_w(x, &w)) {
        return mp_const_false;
    }
    return mp_obj_new_bool(w_isint(w));
}
static MP_DEFINE_CONST_FUN_OBJ_1(f_isint_obj, f_isint);

static const bcd_obj_t pi_obj = {{&bcd_type}, 314159265358979ULL, -14, false};
static const bcd_obj_t e_obj = {{&bcd_type}, 271828182845905ULL, -14, false};

static const mp_rom_map_elem_t bcd_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_bcd) },
    { MP_ROM_QSTR(MP_QSTR_D), MP_ROM_PTR(&bcd_type) },
    { MP_ROM_QSTR(MP_QSTR_pi), MP_ROM_PTR(&pi_obj) },
    { MP_ROM_QSTR(MP_QSTR_e), MP_ROM_PTR(&e_obj) },
    { MP_ROM_QSTR(MP_QSTR_sqrt), MP_ROM_PTR(&f_sqrt_obj) },
    { MP_ROM_QSTR(MP_QSTR_cbrt), MP_ROM_PTR(&f_cbrt_obj) },
    { MP_ROM_QSTR(MP_QSTR_root), MP_ROM_PTR(&f_root_obj) },
    { MP_ROM_QSTR(MP_QSTR_exp), MP_ROM_PTR(&f_exp_obj) },
    { MP_ROM_QSTR(MP_QSTR_ln), MP_ROM_PTR(&f_ln_obj) },
    { MP_ROM_QSTR(MP_QSTR_log10), MP_ROM_PTR(&f_log10_obj) },
    { MP_ROM_QSTR(MP_QSTR_pow10), MP_ROM_PTR(&f_pow10_obj) },
    { MP_ROM_QSTR(MP_QSTR_sin), MP_ROM_PTR(&f_sin_obj) },
    { MP_ROM_QSTR(MP_QSTR_cos), MP_ROM_PTR(&f_cos_obj) },
    { MP_ROM_QSTR(MP_QSTR_tan), MP_ROM_PTR(&f_tan_obj) },
    { MP_ROM_QSTR(MP_QSTR_asin), MP_ROM_PTR(&f_asin_obj) },
    { MP_ROM_QSTR(MP_QSTR_acos), MP_ROM_PTR(&f_acos_obj) },
    { MP_ROM_QSTR(MP_QSTR_atan), MP_ROM_PTR(&f_atan_obj) },
    { MP_ROM_QSTR(MP_QSTR_atan2), MP_ROM_PTR(&f_atan2_obj) },
    { MP_ROM_QSTR(MP_QSTR_sinh), MP_ROM_PTR(&f_sinh_obj) },
    { MP_ROM_QSTR(MP_QSTR_cosh), MP_ROM_PTR(&f_cosh_obj) },
    { MP_ROM_QSTR(MP_QSTR_tanh), MP_ROM_PTR(&f_tanh_obj) },
    { MP_ROM_QSTR(MP_QSTR_asinh), MP_ROM_PTR(&f_asinh_obj) },
    { MP_ROM_QSTR(MP_QSTR_acosh), MP_ROM_PTR(&f_acosh_obj) },
    { MP_ROM_QSTR(MP_QSTR_atanh), MP_ROM_PTR(&f_atanh_obj) },
    { MP_ROM_QSTR(MP_QSTR_floor), MP_ROM_PTR(&f_floor_obj) },
    { MP_ROM_QSTR(MP_QSTR_ceil), MP_ROM_PTR(&f_ceil_obj) },
    { MP_ROM_QSTR(MP_QSTR_trunc), MP_ROM_PTR(&f_trunc_obj) },
    { MP_ROM_QSTR(MP_QSTR_frac), MP_ROM_PTR(&f_frac_obj) },
    { MP_ROM_QSTR(MP_QSTR_rnd), MP_ROM_PTR(&f_rnd_obj) },
    { MP_ROM_QSTR(MP_QSTR_rsig), MP_ROM_PTR(&f_rsig_obj) },
    { MP_ROM_QSTR(MP_QSTR_parts), MP_ROM_PTR(&f_parts_obj) },
    { MP_ROM_QSTR(MP_QSTR_make), MP_ROM_PTR(&f_make_obj) },
    { MP_ROM_QSTR(MP_QSTR_tof), MP_ROM_PTR(&f_tof_obj) },
    { MP_ROM_QSTR(MP_QSTR_isint), MP_ROM_PTR(&f_isint_obj) },
};
static MP_DEFINE_CONST_DICT(bcd_module_globals, bcd_module_globals_table);

const mp_obj_module_t bcd_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&bcd_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_bcd, bcd_user_cmodule);
