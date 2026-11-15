// ncore: small native helpers for card-gcalc.
//
//   ncore.kbd_interrupt()  schedule a KeyboardInterrupt in the main thread
//                          (like Ctrl+C on the REPL).  Safe to call from a
//                          scheduled callback (machine.Timer / Pin IRQ), which
//                          is how the script runner implements Esc / Ctrl+C.
#include "py/runtime.h"

static mp_obj_t ncore_kbd_interrupt(void) {
    mp_sched_keyboard_interrupt();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(ncore_kbd_interrupt_obj, ncore_kbd_interrupt);

static const mp_rom_map_elem_t ncore_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_ncore) },
    { MP_ROM_QSTR(MP_QSTR_kbd_interrupt), MP_ROM_PTR(&ncore_kbd_interrupt_obj) },
};
static MP_DEFINE_CONST_DICT(ncore_globals, ncore_globals_table);

const mp_obj_module_t ncore_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&ncore_globals,
};

MP_REGISTER_MODULE(MP_QSTR_ncore, ncore_module);
