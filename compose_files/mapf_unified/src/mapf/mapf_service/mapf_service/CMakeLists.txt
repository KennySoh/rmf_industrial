cmake_minimum_required(VERSION 3.8)
project(mapf)
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(BUILD_TESTING ON)

add_definitions(-D_MAPDIR_="${CMAKE_CURRENT_LIST_DIR}/maps/")
# for unit testing
# add_definitions(-D_MAPDIR_="${CMAKE_CURRENT_SOURCE_DIR}/test/generated_test_maps/")

set(dep_pkgs
  ament_cmake
  mapf_ros2
  cpprestsdk
  yaml-cpp
  nlohmann_json
)

# find dependencies
foreach(pkg ${dep_pkgs})
  find_package(${pkg} REQUIRED)
endforeach()

include_directories(
  PUBLIC
  include
)

add_library(mapf_ir_interface
SHARED
  src/mapf.cpp
  src/server.cpp
  src/mapf_service.cpp
)

target_link_libraries(mapf_ir_interface
  nlohmann_json::nlohmann_json
  yaml-cpp
)

ament_target_dependencies(mapf_ir_interface 
  yaml-cpp 
  mapf_ros2)

install(
  DIRECTORY include/
  DESTINATION include
)

install(
  TARGETS mapf_ir_interface
  EXPORT export_mapf_ir_interface
  RUNTIME DESTINATION bin
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  INCLUDES DESTINATION include)

ament_export_include_directories(
  include
)
ament_export_libraries(mapf_ir_interface)
ament_export_targets(export_mapf_ir_interface HAS_LIBRARY_TARGET)


add_executable(run_mapf_ir src/run_mapf.cpp)
  target_link_libraries(run_mapf_ir
  PUBLIC cpprestsdk::cpprest -lcrypto mapf_ir_interface)
install(TARGETS
  run_mapf_ir
  DESTINATION lib/${PROJECT_NAME})


add_executable(run_mapf_service src/run_mapf_service.cpp)
target_link_libraries(run_mapf_service
  PUBLIC cpprestsdk::cpprest -lcrypto mapf_ir_interface
)

# target_link_libraries(run_mapf_service
#   cpprestsdk::cpprest
#   -lssl
#   -lcrypto
#   mapf_ir_interface)

install(TARGETS
  run_mapf_service
  DESTINATION lib/${PROJECT_NAME})

add_executable(run_example_client src/run_example_client.cpp)
target_link_libraries(run_example_client
  PUBLIC cpprestsdk::cpprest -lcrypto mapf_ir_interface)
install(TARGETS
  run_example_client
  DESTINATION lib/${PROJECT_NAME})

# Worker subprocess for memory isolation - spawned per request
# DISABLED - reverted to direct call model
# add_executable(mapf_worker src/mapf_worker.cpp)
# target_link_libraries(mapf_worker
#   PUBLIC cpprestsdk::cpprest -lcrypto mapf_ir_interface)
# install(TARGETS
#   mapf_worker
#   DESTINATION lib/${PROJECT_NAME})
# add_executable(run_pgm_generator src/utils/pgm_grid_generator.cpp)

# install(TARGETS
#   run_pgm_generator
#   DESTINATION lib/${PROJECT_NAME})

# find dependencies
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
  add_subdirectory(test)
endif()

ament_package()
