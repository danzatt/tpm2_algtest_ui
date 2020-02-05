cmake_minimum_required(VERSION 3.10)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -pedantic -g")

add_executable(tpm2_algtest_ui main.cpp)
find_package (PkgConfig REQUIRED)

pkg_check_modules(LIBYUI libyui)
if (LIBYUI_FOUND)
	target_link_libraries(tpm2_algtest_ui yui)
	include_directories(${LIBYUI_INCLUDE_DIRS})
else()
	message( FATAL_ERROR "libyui not found" )
endif (LIBYUI_FOUND)
