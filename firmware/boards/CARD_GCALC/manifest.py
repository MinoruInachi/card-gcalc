# Frozen modules for card-gcalc.
freeze("$(PORT_DIR)/modules")
include("$(MPY_DIR)/extmod/asyncio")
require("upysh")
# The calculator application itself.
freeze("$(BOARD_DIR)/../../../src")
