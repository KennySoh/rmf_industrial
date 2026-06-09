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

// MAPF Worker - subprocess that handles a single solve request
// Reads JSON from stdin, outputs result to stdout, then exits
// Memory is fully reclaimed by OS on exit

#include <mapf/mapf.hpp>
#include <iostream>
#include <sstream>
#include <string>

int main(int argc, char * argv[])
{
  // Read entire JSON request from stdin
  std::stringstream buffer;
  buffer << std::cin.rdbuf();
  std::string request = buffer.str();

  if (request.empty()) {
    std::cerr << "Error: No input received" << std::endl;
    return 1;
  }

  // Create solver instance, solve, and output result
  MultiAgentPathFinding mapf(argc, argv);
  std::string result = mapf.test_function(request);

  // Output result to stdout (parent process reads this)
  std::cout << result << std::flush;

  return result.empty() ? 1 : 0;
}
