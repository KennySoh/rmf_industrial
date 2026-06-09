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

#include <mapf/mapf_service.hpp>
#include <stdio.h>

int main(int argc, char * argv[])
{
  printf("argc: %d\n", argc);
  std::string url = "http://localhost:8888";
  if (argc != 3) {
    std::cout << "Revert to default url" << std::endl;
  } else {
    std::string temp_url = "http://";
    std::string arg1(argv[1]);
    std::string arg2(argv[2]);
    url = temp_url + arg1 + ":" + arg2;
  }

  std::cout << "URL: " << url << std::endl;
  MAPFService mapf_service(url, argc, argv);
  while (1) {}
  return 0;
}
