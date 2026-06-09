set(TEST_DIR ${CMAKE_CURRENT_SOURCE_DIR})
add_definitions( -DTEST_DIRECTORY=\"${CMAKE_CURRENT_SOURCE_DIR}/\")

ament_add_gtest(test_${PROJECT_NAME}_solver_map
    ./mapf_solver_map.cpp
)
target_link_libraries(test_${PROJECT_NAME}_solver_map
  mapf_ir_interface
)
