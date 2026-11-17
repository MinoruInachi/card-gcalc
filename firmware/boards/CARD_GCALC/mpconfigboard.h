// card-gcalc: graphing calculator firmware for M5Stack Cardputer-Adv and
// Cardputer.  The Cardputer build is the CARDPUTER variant
// (mpconfigvariant_CARDPUTER.cmake), which defines CARDGCALC_CARDPUTER and
// its own board name.
#ifndef MICROPY_HW_BOARD_NAME
#define MICROPY_HW_BOARD_NAME               "M5Stack Cardputer-Adv (card-gcalc)"
#endif
#define MICROPY_HW_MCU_NAME                 "ESP32S3"

// The Cardputer(-Adv) uses the native USB-Serial/JTAG for the REPL.
#define MICROPY_HW_ENABLE_UART_REPL         (0)

#ifdef CARDGCALC_CARDPUTER
// No internal I2C bus (G8/G9/G11 drive the keyboard's 74HC138): default
// I2C(0) to the Grove port.
#define MICROPY_HW_I2C0_SCL                 (1)
#define MICROPY_HW_I2C0_SDA                 (2)
#else
// Internal I2C bus (keyboard TCA8418, ES8311 codec, BMI270 IMU).
#define MICROPY_HW_I2C0_SCL                 (9)
#define MICROPY_HW_I2C0_SDA                 (8)
#endif

// BLE is not used by the calculator (and NimBLE fails to build on IDF 5.5.4).
#define MICROPY_PY_BLUETOOTH                (0)

// A calculator needs double precision floats.
#define MICROPY_FLOAT_IMPL                  (MICROPY_FLOAT_IMPL_DOUBLE)
#define MICROPY_PY_MATH_SPECIAL_FUNCTIONS   (1)
#define MICROPY_PY_MATH_FACTORIAL           (1)
#define MICROPY_PY_MATH_ISCLOSE             (1)
#define MICROPY_PY_CMATH                    (1)

// Larger initial GC heap: no PSRAM, and the 240x135 RGB565 frame buffer is ~64KB.
#define MICROPY_GC_INITIAL_HEAP_SIZE        (176 * 1024)

// Use the ESP32-S3 built-in USB-Serial/JTAG for the REPL instead of TinyUSB.
// Resetting into the bootloader is then handled by silicon, so esptool can
// always reflash the board even if the firmware is stuck.
#define MICROPY_HW_ENABLE_USBDEV            (0)

// Deeper recursion for Python and the BASIC plugin (default 16KB: ~48 Python
// call levels).
#define MICROPY_TASK_STACK_SIZE             (32 * 1024)
