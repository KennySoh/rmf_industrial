// Copyright 2024 ROS Industrial Consortium Asia Pacific
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#ifndef MAPF__MAPF_HPP
#define MAPF__MAPF_HPP

#include <getopt.h>
#include <mapf/cbs.hpp>
#include <mapf/default_params.hpp>
#include <mapf/ecbs.hpp>
#include <mapf/hca.hpp>
#include <mapf/icbs.hpp>
#include <mapf/ir.hpp>
#include <mapf/pibt.hpp>
#include <mapf/pibt_complete.hpp>
#include <mapf/problem.hpp>
#include <mapf/push_and_swap.hpp>
#include <mapf/revisit_pp.hpp>
#include <mapf/whca.hpp>
#include <mapf/winpibt.hpp>
#include <mapf/utils.hpp>

#include <random>
#include <vector>
#include <iostream>
#include <fstream>
#include <string>
#include <sstream>
#include <algorithm>
#include <unordered_set>

#include <mapf/graph.hpp>
#include <nlohmann/json.hpp>
#include "yaml-cpp/yaml.h"
class MultiAgentPathFinding
{
public:
  MultiAgentPathFinding(int argc, char * argv[])
  : argc_(argc), argv_(argv)
  {}

  std::string test_function(const std::string & request_input)
  {

    nlohmann::json request;

    try {
      request = nlohmann::json::parse(request_input);
    } catch (nlohmann::json::parse_error & ex) {
      std::cerr << "parse error at byte " << ex.byte << std::endl;
      return "";
    }

    if (!request.contains("mapfile")) {
      std::cerr << "Request does not contain field \"mapfile\"" << std::endl;
      return "";
    }

    // We also accept map content input and we dump it into a file to be
    // retrieved later in the maps folder

    if (!request.contains("solver")) {
      std::cerr << "Request does not contain field \"solver\"" << std::endl;
      return "";
    }

    if (!request.contains("max_computation_time")) {
      std::cerr << "Request does not contain field \"max_computation_time\"" << std::endl;
      return "";
    }

    if (!request.contains("max_timestep")) {
      std::cerr << "Request does not contain field \"max_timestep\"" << std::endl;
      return "";
    }

    if (!request.contains("tasks")) {
      std::cerr << "Request does not contain field \"tasks\"" << std::endl;
      return "";
    }

    std::string building_file = request["mapfile"].get<std::string>();
    std::string solver_name = request["solver"].get<std::string>();
    int max_comp_time = request["max_computation_time"].get<int>();
    int max_timestep = request["max_timestep"].get<int>();

    // if the request specifies obstacles, store the points
    // for use when creating a .map file
    std::vector<std::pair<double, double>> request_obstacles;
    if (request.contains("obstacles")) {
      for (const auto & obstacle : request["obstacles"].items()) {
        if (!obstacle.value().contains("coordinate")) {
          std::cerr << "Request field \"obstacles\" does not contain field \"coordinate\"" <<
            std::endl;
          return "";
        }
        if (!obstacle.value()["coordinate"].contains("x") ||
          !obstacle.value()["coordinate"].contains("y"))
        {
          std::cerr << "coordinate does not contain field \"x\" or \"y\"" << std::endl;
          return "";
        }
        request_obstacles.push_back(
          {obstacle.value()["coordinate"]["x"].get<double>(),
            obstacle.value()["coordinate"]["y"].get<double>()});
      }
    }

    // If your map is an RMF1 Yaml file
    std::string mapfile = convert_yaml_to_mapfile(building_file, request_obstacles);
    std::cerr << "mapfile string exists." << std::endl;
    if (mapfile.empty()) {
      std::cerr << "Error converting building.yaml to .map file." << std::endl;
      return "";
    } else {
      std::cout << "Successfully created mapfile: " << mapfile << std::endl;
    }

    std::vector<std::string> agents;

    std::vector<std::pair<std::pair<int, int>, std::pair<int, int>>> tasks;

    for (const auto & agent : request["tasks"].items()) {
      if (!agent.value().contains("agent_name")) {
        std::cerr << "Task does not contain field \"agent_name\"" << std::endl;
        return "";
      }

      if (!agent.value().contains("start_position")) {
        std::cerr << "Task does not contain field \"start_position\"" << std::endl;
        return "";
      }

      if (!agent.value().contains("end_position")) {
        std::cerr << "Task does not contain field \"end_position\"" << std::endl;
        return "";
      }

      if (!agent.value()["start_position"].contains("x") ||
        !agent.value()["start_position"].contains("y"))
      {
        std::cerr << "Start Position does not contain field \"x\" or \"y\"" << std::endl;
        return "";
      }

      if (!agent.value()["end_position"].contains("x") ||
        !agent.value()["end_position"].contains("y"))
      {
        std::cerr << "End Position does not contain field \"x\" or \"y\"" << std::endl;
        return "";
      }
      std::pair<double, double> start_pos(
        agent.value()["start_position"]["x"].get<double>(),
        agent.value()["start_position"]["y"].get<double>()
      );
      std::pair<double, double> end_pos(
        agent.value()["end_position"]["x"].get<double>(),
        agent.value()["end_position"]["y"].get<double>()
      );
      // Need to validate points first.
      // Invalid points being fed into the mapf solver will result in an exit call
      if (!valid(start_pos) || !valid(end_pos)) {
        std::cerr << "Agent: " << agent.value()["agent_name"].get<std::string>() <<
          " has invalid start and/or end points!" << std::endl;
        return "";
      }
      agents.push_back(agent.value()["agent_name"].get<std::string>());
      tasks.push_back(
        std::pair<std::pair<int, int>, std::pair<int, int>>(
          real_to_scaled_map_[start_pos],
          real_to_scaled_map_[end_pos]));
    }


    // // Test scenario
    // std::vector<std::string> agents{"agent_1", "agent_2"};
    // std::vector<std::pair<std::pair<int, int> ,std::pair<int, int>>> custom_start_goals;
    // custom_start_goals.push_back(
    //   {
    //     real_to_scaled_map_[std::pair<int, int>{30,60}],
    //     real_to_scaled_map_[std::pair<int, int>{30,30}]
    //   });
    // custom_start_goals.push_back(
    //   {
    //     real_to_scaled_map_[std::pair<int, int>{300,90}],
    //     real_to_scaled_map_[std::pair<int, int>{300,60}]
    //   });

    // return plan_path(
    //   mapfile,
    //   agents,
    //   custom_start_goals,
    //   "ECBS",
    //   argc_,
    //   argv_,
    //   5000,
    //   1000
    // );

    return plan_path(
      mapfile,
      agents,
      tasks,
      solver_name,
      argc_,
      argv_,
      max_comp_time,
      max_timestep
    );
  }

  ~MultiAgentPathFinding() {}

  // Temporary function to convert building.yaml file to MAPF-IR map file.
  std::string convert_yaml_to_mapfile(
    const std::string & yaml_file,
    const std::vector<std::pair<double, double>> & request_obstacles)
  {
    std::string suffix = yaml_file.substr(yaml_file.length() - 4, 4);
    if (suffix.compare("yaml") != 0) {
      std::cerr <<
        "Building File not in correct format. supposed to be yaml, instead: "
                << suffix << std::endl;
      return "";
    }
    // read map file
    std::ifstream file(yaml_file);
    std::string mapfile;
    YAML::Node config;

    if (file.good()) {
      config = YAML::LoadFile(yaml_file);
      mapfile = yaml_file.substr(0, yaml_file.length() - 4) + "map";
    } else {
    #ifdef _MAPDIR_
      std::ifstream file(_MAPDIR_ + yaml_file);
      if (!file.good()) {
        std::cerr <<
          "Could not find Building File from path: " << _MAPDIR_ + yaml_file << std::endl;
        return "";
      }
      config = YAML::LoadFile(_MAPDIR_ + yaml_file);
      mapfile = _MAPDIR_ + yaml_file.substr(0, yaml_file.length() - 4) + "map";
      std::cout << "mapfile: " << mapfile << std::endl;
    #else
      std::cerr <<
        "Could not find Building File from path: " << mapfile << std::endl;
      return "";
    #endif
    }
    // clearing all maps in the case where map is redefined (prevents memory leak)
    obstacles_.clear();
    node_map_.clear();
    reversed_node_map_.clear();
    real_to_scaled_map_.clear();
    scaled_to_real_map_.clear();
    // YAML::Node config = YAML::LoadFile(yaml_file);
    YAML::Node level_node = config["levels"];
    std::unordered_set<int> seen_nodes;
    // We now have a map node, so let's iterate through:
    for (auto it = level_node.begin(); it != level_node.end(); ++it) {
      YAML::Node key = it->first;
      YAML::Node value = it->second;
      if (key.Type() == YAML::NodeType::Scalar && value.Type() == YAML::NodeType::Map) {
        if (key.as<std::string>().compare("warehouse") == 0) {
          for (auto nested_it = value.begin(); nested_it != value.end(); ++nested_it) {
            YAML::Node nested_key = nested_it->first;
            YAML::Node nested_value = nested_it->second;
            if (nested_key.Type() == YAML::NodeType::Scalar &&
              nested_value.Type() == YAML::NodeType::Sequence)
            {
              if (nested_key.as<std::string>().compare("lanes") == 0) {
                int counter = 0;
                YAML::Node lanes = nested_value;
                for (YAML::iterator it = lanes.begin(); it != lanes.end(); ++it) {
                  YAML::Node lane_data = *it;
                  if (lane_data.Type() == YAML::NodeType::Sequence && lane_data.size() == 3) {
                    int node_1_index = lane_data[0].as<int>(); // First node it is connected to
                    int node_2_index = lane_data[1].as<int>(); // Second node it is connected to
                    // std::cout << "Edge " << std::to_string(counter) << " is connected to Nodes "
                    //   << std::to_string(node_1_index) << " and " << std::to_string(node_2_index)
                    //   << std::endl;
                    // used to keep track of traffic lane points
                    // if a point does not have any traffic lane associated with it,
                    // it is an obstacle
                    seen_nodes.emplace(node_2_index);
                    seen_nodes.emplace(node_1_index);
                    counter++;
                  }
                }
              } else if (nested_key.as<std::string>().compare("vertices") == 0) {
                // std::map<std::string, std::pair<double, double>> points;
                std::vector<std::pair<double, double>> points;
                YAML::Node nodes = nested_value;
                int counter = 0;
                for (YAML::iterator it = nodes.begin(); it != nodes.end(); ++it) {
                  YAML::Node node_data = *it;
                  if (node_data.Type() == YAML::NodeType::Sequence && node_data.size() == 5) {
                    double x_coord = node_data[0].as<double>();
                    double y_coord = node_data[1].as<double>();
                    std::string node_id = node_data[3].as<std::string>();
                    node_map_[node_id] = std::pair<double, double>{x_coord, y_coord};
                    reversed_node_map_[std::pair<double, double>{x_coord, y_coord}] = node_id;
                    // points[node_id] = std::pair<double, double>{x_coord, y_coord};
                    if (!seen_nodes.count(counter)) {
                      obstacles_.emplace(node_id);
                    }
                    points.push_back(std::pair<double, double>{x_coord, y_coord});
                    // std::cout << "Node " << node_id << " of index " << std::to_string(counter)
                    //   <<  " is at (" << std::to_string(x_coord) << "," << std::to_string(y_coord)
                    //   << ")" << std::endl;
                    counter++;
                  }
                }
                // getting cols and rows
                // std::vector<std::pair<double, double>> vrow;
                // std::vector<std::pair<double, double>> vcol;
                // std::unique_copy(
                //   points.begin(), points.end(), std::back_inserter(vcol),
                //   [](const std::pair<double, double> & lhs, const std::pair<double, double> & rhs)
                //   {
                //     return lhs.first != rhs.first;
                //   });
                // std::unique_copy(
                //   points.begin(), points.end(), std::back_inserter(vrow),
                //   [](const std::pair<double, double> & lhs, const std::pair<double, double> & rhs)
                //   {
                //     return lhs.second != rhs.second;
                //   });

                // temporary fix, will need to implement a way to obtain rows and columns dynamically
                if (!config["rows"] || !config["columns"]) {
                  std::cerr <<
                    "Missing rows and/or columns parameter(s) in Building File! Please specify:\nRows: X\nColumns: Y\nin this format in the first 2 lines of the Building File!"
                            << std::endl;
                  return "";
                }
                YAML::Node vrows = config["rows"];
                YAML::Node vcols = config["columns"];
                int rows = vrows.as<int>();
                int cols = vcols.as<int>();

                auto sorted_real_points = sort_into_grid(points, cols, rows);
                // connect_points_in_grid(output);
                std::vector<std::vector<std::string>> output{
                  cols, std::vector<std::string>(rows, ".")};

                std::vector<std::vector<std::pair<int, int>>> simple_grid;

                int y_val = 0;
                for (const auto & row : output) {
                  int x_val = 0;
                  std::vector<std::pair<int, int>> temp_row;
                  for (const auto & entry : row) {
                    temp_row.push_back(std::pair<int, int>{x_val, y_val});
                    x_val++;
                  }
                  simple_grid.push_back(temp_row);
                  y_val++;
                }

                if (sorted_real_points.size() != simple_grid.size()) {
                  return "";
                }
                for (int i = 0; i < sorted_real_points.size(); i++) {
                  if (sorted_real_points[i].size() != simple_grid[i].size()) {
                    return "";
                  }
                  for (int j = 0; j < sorted_real_points[i].size(); j++) {
                    real_to_scaled_map_[sorted_real_points[i][j]] = simple_grid[i][j];
                    scaled_to_real_map_[simple_grid[i][j]] = sorted_real_points[i][j];
                    // std::cout << "(" << sorted_real_points[i][j].first << "," << sorted_real_points[i][j].second <<")" << " IS "
                    // << "(" << simple_grid[i][j].first << "," << simple_grid[i][j].second << ")" << std::endl;
                  }
                }
                // obstacles from the request will be processed after recording
                // points from the building.yaml file
                for (const auto & point : request_obstacles) {
                  if (valid(point)) {
                    obstacles_.emplace(reversed_node_map_[point]);
                  } else {
                    std::cerr << "Request field \"obstacle\" of point x: " << point.first
                              << " y: " << point.second << " is an invalid or duplicate point!" <<
                      std::endl;
                  }
                }
                // replacing str obj of points with obstacles identified
                for (const auto & point : obstacles_) {
                  auto coordinate =
                    real_to_scaled_map_[std::pair<double, double>(
                        node_map_[point].first,
                        node_map_[point].second)];
                  output[coordinate.second][coordinate.first] = "T";  // row-major order [y][x]
                }

                if (create_mapfile(cols, rows, output, mapfile)) {
                  return mapfile;
                } else {
                  std::cerr << "Mapfile creation failed" << std::endl;
                  return "";
                }


                /* Not used but maybe useful?
                  #include <climits>
                  int max_x = INT_MIN;
                  int max_y = INT_MIN;

                  std::vector<std::pair<int, int>> points;

                  YAML::Node nodes = nested_value;
                  for (YAML::iterator it = nodes.begin(); it != nodes.end(); ++it) {
                    YAML::Node node_data = *it;
                    if(node_data.Type() == YAML::NodeType::Sequence && node_data.size() == 5){
                      int x_coord =node_data[0].as<int>();
                      int y_coord =node_data[1].as<int>();
                      points.push_back(std::pair<int, int>{x_coord, y_coord});
                      if(x_coord > max_x){
                        max_x = x_coord;
                      }
                      if(y_coord > max_y){
                        max_y = y_coord;
                      }
                      std::string node_id = node_data[3].as<std::string>();
                      std::cout << "Node " << node_id << " of index " << std::to_string(counter)
                        <<  " is at (" << std::to_string(x_coord) << "," << std::to_string(y_coord)
                        << ")" << std::endl;
                      counter++;
                      std::cout << "counter: " << std::to_string(counter) << std::endl;
                    }
                  }

                  // connect_points_in_grid(output);
                  int col, row;
                  col = row = sqrt(total_nodes);
                  return create_mapfile(col, row, output, mapfile);


                  int total_nodes = (max_x + 1) * (max_y + 1);
                  std::cout << "Total Nodes: " << std::to_string(total_nodes) << std::endl;
                  std::vector<std::vector<std::string>> output{
                    max_y + 1, std::vector<std::string>(max_x + 1,"T")};
                  for(const auto& point : points){
                    output[point.second][point.first] = ".";
                  }
                  // connect_points_in_grid(output);
                  int col, row;
                  col = row = sqrt(total_nodes);
                  return create_mapfile(col, row, output, mapfile);
                */
              }
            }
          }
        }
      }
    }
    return "";
  }

  // Sorts a vector of 2d points into a 2d grid.
  std::vector<std::vector<std::pair<double, double>>> sort_into_grid(
    std::vector<std::pair<double,
    double>> input, const int & cols, const int & rows)
  {
    auto points = input;
    // std::stable_sort(
    //   points.begin(),
    //   points.end(),
    //   [](const std::pair<int, int> & lhs, const std::pair<int, int> & rhs)
    //   {
    //     return lhs.second < rhs.second;
    //   });

    // std::stable_sort(
    //   points.begin(),
    //   points.end(),
    //   [](const std::pair<int, int> & lhs, const std::pair<int, int> & rhs)
    //   {
    //     return lhs.first < rhs.first;
    //   });
    std::vector<std::vector<std::pair<double, double>>> output{
      cols, std::vector<std::pair<double, double>>(
        rows, std::pair<double, double>{0, 0})};

    for (int col = 0; col < cols; col++) {
      for (int row = 0; row < rows; row++) {
        output[col][row] = points[row + rows * col];  // row-major order: x + x_N*y
      }
    }
    // std::cout << "AFTER" << std::endl;
    // for(const auto& point : points){
    //   std::cout << "(" << std::to_string(point.first) << "," << std::to_string(point.second) << ") ,";
    // }
    return output;
  }


  // Not used but maybe useful?
  std::vector<std::vector<std::string>> connect_points_in_grid(
    std::vector<std::vector<std::string>> grid)
  {
    std::vector<std::vector<std::string>> output = grid;
    // Step 1, Create paths Vertically with "*"
    for (int row_index = 0; row_index < output.size(); row_index++) {
      for (int col_index = 0; col_index < output[row_index].size(); col_index++) {
        if (row_index != 0) {
          if (
            output[row_index - 1][col_index].compare(".") == 0 ||
            output[row_index - 1][col_index].compare("*") == 0)
          {
            if (output[row_index][col_index].compare(".") != 0) {
              output[row_index][col_index] = "*";
            }
          }
        }
      }
    }

    // Step 2, Create paths horizontally with "."
    for (int row_index = 0; row_index < output.size(); row_index++) {
      for (int col_index = 0; col_index < output[row_index].size(); col_index++) {
        if (col_index != 0) {
          if (output[row_index][col_index - 1].compare(".") == 0) {
            output[row_index][col_index] = ".";
          }
        }
      }
    }
    // Step 3, replace the "*" with "."
    for (int row_index = 0; row_index < output.size(); row_index++) {
      for (int col_index = 0; col_index < output[row_index].size(); col_index++) {
        if (output[row_index][col_index].compare("*") == 0) {
          output[row_index][col_index] = ".";
        }
      }
    }
    return output;
  }

  bool convert_pgm_to_mapfile(
    const std::string & pgm_file,
    const std::string & mapfile)
  {
    int row = 0;
    int col = 0;
    int maxvalue = 0;
    char magicnumber_1, magicnumber_2;
    std::string inputLine = "";
    std::stringstream ss;

    std::ifstream infile;
    infile.open(pgm_file);

    infile >> magicnumber_1 >> magicnumber_2;
    if (magicnumber_1 == 'P' && magicnumber_2 == '5') {
      getline(infile, inputLine);
      std::cout << "Version : P5" << std::endl;
    } else {
      std::cout << " The File Version is Wrong" << std::endl;
      return false;
    }

    std::getline(infile, inputLine);
    std::cout << "Comment : " << inputLine << std::endl;
    ss << infile.rdbuf();
    ss >> col >> row;
    std::cout << "Width and Height : " << col << " " << row << std::endl;
    ss >> maxvalue;

    if (maxvalue == 255) {
      std::cout << "Maximum Value : " << maxvalue << std::endl;
    } else {
      std::cout << "Maximum Value Error!!\nYour Maximum Value: " << maxvalue << std::endl;
      return false;
    }

    std::vector<std::vector<std::string>> output;

    for (int i = 0; i < row; i++) {
      for (int j = 0; j < col; j++) {
        std::vector<std::string> row_vec;
        uint8_t content;
        ss >> content;
        if (content == 255) {
          row_vec.push_back(".");
        } else {
          row_vec.push_back("T");
        }
        output.push_back(row_vec);
      }
    }

    infile.close();
    return create_mapfile(col, row, output, mapfile);
  }

// Only needed because of MAPF-IR
  bool create_mapfile(
    const int & height,
    const int & width,
    std::vector<std::vector<std::string>> map,
    // std::vector<std::string> map,
    const std::string & filepath)
  {
    std::ofstream outfile(filepath);

    outfile << "height " << std::to_string(height) << std::endl;
    outfile << "width " << std::to_string(width) << std::endl;
    outfile << "map" << std::endl;

    int counter = 1;

    for (const auto & row : map) {
      for (const auto & entry : row) {
        outfile << entry;
      }
      outfile << std::endl;
    }

    // for(const auto& entry : map){
    //     outfile << entry;
    //     if(counter == width){
    //         outfile << std::endl;
    //         counter = 1;
    //     }else{
    //         counter++;
    //     }
    // }
    outfile.close();
    return true;
  }

  // used to check if the point is a valid coordinate on the map
  bool valid(const std::pair<double, double> & point)
  {
    if (!reversed_node_map_.count(point)) {
      return false;
    }
    if (obstacles_.count(reversed_node_map_[point])) {
      return false;
    }
    return true;
  }

  [[nodiscard]] std::string plan_path(
    const std::string & mapfile,
    const std::vector<std::string> & agents,
    const std::vector<std::pair<std::pair<int, int>, std::pair<int, int>>> & custom_start_goals,
    const std::string & solver_name,
    int argc, char * argv[],
    const int & max_comp_time,
    const int & max_timestep,
    bool verbose = false)
  {
    std::cout << "Creating Problem from mapfile " << mapfile << "......" << std::endl;
    Problem problem = create_problem(
      mapfile, agents.size(), custom_start_goals, max_comp_time, max_timestep);

    std::cout << "Problem Created" << std::endl;
    if (max_comp_time != -1) {problem.setMaxCompTime(max_comp_time);}

    std::cout << "Getting Solver......" << std::endl;
    std::unique_ptr<Solver> solver = getSolver(
      solver_name,
      &problem,
      verbose,
      argc,
      argv);
    std::cout << "Solver Gotten" << std::endl;

    std::cout << "Solving Problem......" << std::endl;
    try {
      solver->solve();
    } catch (...) {
      std::cout << "Error " << std::endl;
    }
    std::cout << "Solver Solved " << std::endl;

    if (solver->succeed() && !solver->getSolution().validate(&problem)) {
      std::cout << "error@app: invalid results" << std::endl;
      return "";
    }
    solver->printResult();

    // Get full solution
    return export_solution(
      agents, solver->getSolution());
    // std::remove(mapfile.c_str()); // delete file
  }

  std::string export_solution(
    const std::vector<std::string> & agents,
    Plan solution)
  {
    std::map<std::string, std::vector<std::pair<double, double>>> solution_map;
    // Get full solution
    for (int t = 0; t <= solution.getMakespan(); ++t) {
      auto c = solution.get(t);
      if (agents.size() != c.size()) {
        return "";
      }
      int counter = 0;
      for (auto v : c) {
        solution_map[agents[counter]].push_back(
          scaled_to_real_map_[std::pair<int, int>{v->pos.x, v->pos.y}]);
        counter++;
      }
    }

    nlohmann::json msg_json;
    auto plan_array = nlohmann::json::array();
    for (const auto & agent: solution_map) {
      nlohmann::json plan_json;
      plan_json["agent_name"] = agent.first;
      auto steps_array = nlohmann::json::array();
      nlohmann::json step_from_json;
      int timestep = 0;
      for (auto step : agent.second) {
        nlohmann::json step_to_json;
        // step_to_json["x"] = step.first;
        // step_to_json["y"] = step.second;
        step_to_json["node"] = reversed_node_map_[step];

        if (step_from_json.contains("node")) {
          // if (step_from_json.contains("x") && step_from_json.contains("y")) {
          nlohmann::json step_json;
          step_json["step_from"] = step_from_json;
          step_json["step_to"] = step_to_json;
          step_json["timestep"] = timestep;
          steps_array.push_back(step_json);
          timestep++;
        }
        step_from_json = step_to_json;
      }
      plan_json["steps"] = steps_array;
      plan_array.push_back(plan_json);
    }
    return plan_array.dump();
  }

//   void solve_problem(std::unique_ptr<Solver> solver, Problem problem)
//   {
//     solver->solve();
//     if (solver->succeed() && !solver->getSolution().validate(&problem)) {
//       std::cout << "error@app: invalid results" << std::endl;
//       return ;
//     }
//     solver->printResult();
//     // solver->makeLog(output_file);
//     // std::cout << "save result as " << output_file << std::endl;
//   }

  Problem create_problem(
    const std::string & mapfile,
    const int & num_agents,
    const std::vector<
      std::pair<
        std::pair<int, int>, std::pair<int, int>>> & custom_s_g,
    const int max_comp_time,
    const int max_timestep,
    const int & seed = 0,
    const bool & well_formed = true,
    const bool & random_problem = false)
  {
    return Problem(
      mapfile,
      num_agents,
      custom_s_g,
      seed,
      random_problem,
      well_formed,
      max_comp_time,
      max_timestep
    );
  }

  std::unique_ptr<Solver> getSolver(
    const std::string solver_name, Problem * P,
    bool verbose, int argc, char * argv[])
  {
    std::unique_ptr<Solver> solver;
    if (solver_name == "PIBT") {
      solver = std::make_unique<PIBT>(P);
    } else if (solver_name == "winPIBT") {
      solver = std::make_unique<winPIBT>(P);
    } else if (solver_name == "HCA") {
      solver = std::make_unique<HCA>(P);
    } else if (solver_name == "WHCA") {
      solver = std::make_unique<WHCA>(P);
    } else if (solver_name == "CBS") {
      solver = std::make_unique<CBS>(P);
    } else if (solver_name == "ICBS") {
      solver = std::make_unique<ICBS>(P);
    } else if (solver_name == "PIBT_COMPLETE") {
      solver = std::make_unique<PIBT_COMPLETE>(P);
    } else if (solver_name == "ECBS") {
      solver = std::make_unique<ECBS>(P);
    } else if (solver_name == "RevisitPP") {
      solver = std::make_unique<RevisitPP>(P);
    } else if (solver_name == "PushAndSwap") {
      solver = std::make_unique<PushAndSwap>(P);
    } else if (solver_name == "IR") {
      solver = std::make_unique<IR>(P);
    } else if (solver_name == "IR_SINGLE_PATHS") {
      solver = std::make_unique<IR_SINGLE_PATHS>(P);
    } else if (solver_name == "IR_FIX_AT_GOALS") {
      solver = std::make_unique<IR_FIX_AT_GOALS>(P);
    } else if (solver_name == "IR_FOCUS_GOALS") {
      solver = std::make_unique<IR_FOCUS_GOALS>(P);
    } else if (solver_name == "IR_MDD") {
      solver = std::make_unique<IR_MDD>(P);
    } else if (solver_name == "IR_BOTTLENECK") {
      solver = std::make_unique<IR_BOTTLENECK>(P);
    } else if (solver_name == "IR_HYBRID") {
      solver = std::make_unique<IR_HYBRID>(P);
    } else {
      std::cout << "warn@app: "
                << "unknown solver name, " + solver_name + ", continue by PIBT"
                << std::endl;
      solver = std::make_unique<PIBT>(P);
    }
    std::cout << "Setting Params: " << std::to_string(argc) << std::endl;
    solver->setParams(argc, argv);
    std::cout << "Params Set" << std::endl;

    solver->setVerbose(verbose);
    return solver;
  }

  std::map<std::pair<double, double>, std::pair<int, int>> real_to_scaled_map_; // real world coordinate to simple grid

  std::map<std::string, std::pair<double, double>> node_map_;

  std::map<std::pair<double, double>, std::string> reversed_node_map_;

  std::map<std::pair<int, int>, std::pair<double, double>> scaled_to_real_map_; // simple grid to real world coordinate

  std::unordered_set<std::string> obstacles_;

  int argc_;

  char ** argv_;

  std::string pgm_mapfile_;
};

#endif //MAPF__MAPF_HPP
