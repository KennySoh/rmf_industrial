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

#ifndef MAPF__GRAPH_HPP
#define MAPF__GRAPH_HPP

#include <graph.hpp>
namespace MAPF
{
class Grid : public Graph
{
private:
  int width;
  int height;

public:
  Grid() {}
  ~Grid() {}

  bool existNode(int id) const;
  bool existNode(int x, int y) const;
  Node * getNode(int id) const;
  Node * getNode(int x, int y) const;

  int dist(const Node * const v, const Node * const u) const
  {
    return v->manhattanDist(u);
  }

//   std::string getMapFileName() const {return map_file;}
  int getWidth() const {return width;}
  int getHeight() const {return height;}
};
}

#endif //MAPF__MAPF_HPP
