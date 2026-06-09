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

  #include <iostream>
  #include <iomanip>
  #include <fstream>
  #include <cstring>
  #include <sstream>
  #include <string>


#include <mapf/server.hpp>

using namespace std;
int main(int argc, char * argv[])
{
  const int buffer_thickness = 0;
  const int grid_width = 100;
  const int grid_height = 100;
  const int maxval = 255;
  string filename;

  std::fstream file;
  file.open(
    "output2.pgm", std::ios_base::out |
    std::ios_base::binary |
    std::ios_base::trunc);

  file << "P5" << endl;
  file << "# Created by Alper BALMUMCU" << endl;
  file << grid_width + buffer_thickness * 2 << " " << grid_height + buffer_thickness * 2 << endl;
  file << maxval << endl;

  for (int i = 0; i < grid_height + buffer_thickness * 2; i++) {
    for (int j = 0; j < grid_width + buffer_thickness * 2; j++) {
      if (i < buffer_thickness || j < buffer_thickness) {
        file << static_cast<char>(1);
      } else if (i < grid_height + buffer_thickness * 2 && i >= grid_height + buffer_thickness) {
        file << static_cast<char>(1);
      } else if (j < grid_width + buffer_thickness * 2 && j >= grid_width + buffer_thickness) {
        file << static_cast<char>(1);
      } else {
        file << static_cast<char>(255);
      }
    }
  }
  file.close();
}
