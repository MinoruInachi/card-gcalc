# bcd: 15-digit decimal floating point for the calculator apps
add_library(usermod_bcd INTERFACE)
target_sources(usermod_bcd INTERFACE ${CMAKE_CURRENT_LIST_DIR}/bcd.c)
target_include_directories(usermod_bcd INTERFACE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(usermod INTERFACE usermod_bcd)
