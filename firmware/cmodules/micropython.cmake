# User C modules for card-gcalc: pass USER_C_MODULES=<this file> to make.
include(${CMAKE_CURRENT_LIST_DIR}/ncore/micropython.cmake)
# bcd: 15-digit decimal floating point used by the calculator apps
include(${CMAKE_CURRENT_LIST_DIR}/bcd/micropython.cmake)
# ulab (numpy-like arrays): fetched into deps/ulab by tools/setup.sh
include(${CMAKE_CURRENT_LIST_DIR}/../../deps/ulab/code/micropython.cmake)
# ulab expands its loops for every dtype combination; compile it for size
# (about half the flash of the default -O2 build).
set_source_files_properties(${ULAB_SOURCES} DIRECTORY ${CMAKE_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}
    PROPERTIES COMPILE_OPTIONS "-Os")
