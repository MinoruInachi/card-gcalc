add_library(usermod_ncore INTERFACE)
target_sources(usermod_ncore INTERFACE ${CMAKE_CURRENT_LIST_DIR}/ncore.c)
target_include_directories(usermod_ncore INTERFACE ${CMAKE_CURRENT_LIST_DIR})
target_link_libraries(usermod INTERFACE usermod_ncore)
