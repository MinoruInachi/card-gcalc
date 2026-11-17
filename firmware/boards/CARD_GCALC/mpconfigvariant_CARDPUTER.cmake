# Variant for the original M5Stack Cardputer (keyboard read through a
# 74HC138 GPIO matrix instead of the TCA8418 of the Cardputer-Adv).
#   make BOARD_DIR=.../CARD_GCALC BOARD_VARIANT=CARDPUTER
list(APPEND MICROPY_DEF_BOARD
    "MICROPY_HW_BOARD_NAME=\"M5Stack Cardputer (card-gcalc)\""
    CARDGCALC_CARDPUTER=1
)

if(NOT MICROPY_USER_FROZEN_MANIFEST)
    set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest_cardputer.py)
endif()
