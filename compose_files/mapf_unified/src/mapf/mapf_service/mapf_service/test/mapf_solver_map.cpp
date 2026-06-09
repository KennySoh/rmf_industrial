#include "gtest/gtest.h"
#include <filesystem>
#include <fstream>
#include <chrono>
#include <vector>
#include <nlohmann/json.hpp>

#include "mapf/mapf.hpp"

bool compare_files(const std::string & file1, const std::string & file2)
{
  std::ifstream f1(file1), f2(file2);
  if (!f1.is_open()) {
    std::cout << file1 << " does not exist!" << "\n";
    return false;
  }
  if (!f2.is_open()) {
    std::cout << file2 << " does not exist!" << "\n";
    return false;
  }
  std::string f1_line, f2_line;
  while (std::getline(f1, f1_line) && std::getline(f2, f2_line)) {
    if (f1_line != f2_line) {
      return false;
    }
  }
  return true;
}

class TESTMAPFSOLVER : public ::testing::Test
{
protected:
  void SetUp() override
  {
    mapf = std::make_unique<MultiAgentPathFinding>(0, nullptr);
    // directory of test building.yaml files
    test_yaml_file_dir = std::string(TEST_DIRECTORY) + "generated_test_maps/";
    // directory of expected outputs
    expected_output_dir = std::string(TEST_DIRECTORY) + "test_maps/";

  }
  std::string test_yaml_file_dir;
  std::string expected_output_dir;
  std::unique_ptr<MultiAgentPathFinding> mapf;
  std::vector<std::pair<double, double>> obstacles;
};

TEST_F(TESTMAPFSOLVER, map_building)
{
  // standard 20 x 20 map with 4 removed points - P21, P41, P61, P81
  std::string map_file = mapf->convert_yaml_to_mapfile(
    test_yaml_file_dir + "warehouse.building.yaml", obstacles);
  bool same = compare_files(
    test_yaml_file_dir + "warehouse.building.map",
    expected_output_dir + "warehouse.building.map");
  EXPECT_TRUE(same);

  // validate points (uses scaled points as reference)
  EXPECT_FALSE(mapf->valid(std::pair<int, int>(1, 3)));
  EXPECT_FALSE(mapf->valid(std::pair<int, int>(4, 12)));
  EXPECT_TRUE(mapf->valid(std::pair<int, int>(4, 20)));

  // convert 5x3 .yaml file
  mapf->convert_yaml_to_mapfile(test_yaml_file_dir + "5x3.building.yaml", obstacles);
  EXPECT_TRUE(
    compare_files(
      test_yaml_file_dir + "5x3.building.map",
      expected_output_dir + "5x3.building.map"));

  // convert .yaml file with floating points
  mapf->convert_yaml_to_mapfile(test_yaml_file_dir + "fp.building.yaml", obstacles);
  EXPECT_TRUE(
    compare_files(
      test_yaml_file_dir + "fp.building.map",
      expected_output_dir + "warehouse.building.map"));
}

TEST_F(TESTMAPFSOLVER, path_planning)
{
  std::string test_routes_dir = test_yaml_file_dir + "routes/";
  std::vector<std::pair<std::pair<int, int>, std::pair<int, int>>> custom_start_goal;
  std::vector<std::string> agents {1, "KIV001"};
  std::pair<std::pair<int, int>, std::pair<int, int>> invalid_goal = std::make_pair(
    std::make_pair(1, 3), std::make_pair(0, 0));   // (1,3) is P61 (0,0) is P0
  custom_start_goal.push_back(invalid_goal);
  mapf->convert_yaml_to_mapfile(test_yaml_file_dir + "warehouse.building.yaml", obstacles);

  // first case: invalid start point
  EXPECT_EXIT(
    {mapf->plan_path(
        test_yaml_file_dir + "warehouse.building.map", agents, custom_start_goal, "ECBS", 0,
        nullptr, 5000, 1000);}, testing::ExitedWithCode(1),
    "");

  // second case: valid start point
  custom_start_goal.pop_back();
  std::pair<std::pair<int, int>, std::pair<int, int>> agent_1_goal = std::make_pair(
    std::make_pair(1, 5), std::make_pair(0, 0));   // (1,5) is P101 (0,0) is P0
  custom_start_goal.push_back(agent_1_goal);
  auto new_path = mapf->plan_path(
    test_yaml_file_dir + "warehouse.building.map", agents,
    custom_start_goal, "ECBS", 0, nullptr, 5000, 1000);
  std::string output_file_name = test_routes_dir + "ECBS_plan_path.txt";
  std::ofstream outputfile(output_file_name);
  outputfile << new_path;
  outputfile.close();
  EXPECT_TRUE(compare_files(output_file_name, expected_output_dir + "ECBS_plan_path.txt"));

  // third case: 2 agents
  agents.push_back("KIV002");
  std::pair<std::pair<int, int>, std::pair<int, int>> agent_2_goal = std::make_pair(
    std::make_pair(5, 1), std::make_pair(0, 1));
  custom_start_goal.push_back(agent_2_goal);
  new_path = mapf->plan_path(
    expected_output_dir + "warehouse.building.map", agents, custom_start_goal,
    "ECBS", 0, nullptr, 5000, 1000);
  output_file_name = test_routes_dir + "ECBS_2_agents_plan_path.txt";
  outputfile.open(output_file_name);
  outputfile << new_path;
  outputfile.close();
  EXPECT_TRUE(
    compare_files(
      output_file_name,
      expected_output_dir + "ECBS_2_agents_plan_path.txt"));
}

TEST_F(TESTMAPFSOLVER, full_class_test)
{
  std::string test_routes_dir = test_yaml_file_dir + "routes/";
  //classic building.yaml
  nlohmann::json task;
  task["mapfile"] = test_yaml_file_dir + "warehouse.building.yaml";
  task["solver"] = "ECBS";
  task["max_computation_time"] = 5000;
  task["max_timestep"] = 1000;
  task["tasks"] =
  {{{"agent_name", "KIV001"}, {"start_position", {{"x", 4}, {"y", 20}}},
    {"end_position", {{"x", 0}, {"y", 0}}}}};
  std::string path = mapf->test_function(task.dump());
  std::string output_file_name = test_routes_dir + "ECBS_full_plan_path.txt";
  std::ofstream outputfile(output_file_name);
  outputfile << path;
  outputfile.close();
  EXPECT_TRUE(compare_files(output_file_name, expected_output_dir + "ECBS_plan_path.txt"));
  // add obstacles
  task["obstacles"] = {{{"coordinate", {{"x", 4}, {"y", 20}}}}};
  path = mapf->test_function(task.dump());
  EXPECT_TRUE("" == path);
}
