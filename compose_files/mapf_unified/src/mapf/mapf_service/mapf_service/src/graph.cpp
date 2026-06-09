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

#include <mapf/graph.hpp>
namespace MAPF
{
Grid::Grid(
  int width,
  int height)
: Graph()
{
  if (!(width > 0 && height > 0)) {
    halt("failed to load width/height.");
  }
  // create nodes
  V = Nodes(width * height, nullptr);
  for (int x = 0; x < width; ++x) {
    for (int y = 0; y < height; ++y) {
      int id = width * y + x;
      Node * v = new Node(id, x, y);
      V[id] = v;
    }
  }

  // create edges
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      if (!existNode(x, y)) {continue;}
      Node * v = getNode(x, y);
      // left
      if (existNode(x - 1, y)) {v->neighbor.push_back(getNode(x - 1, y));}
      // right
      if (existNode(x + 1, y)) {v->neighbor.push_back(getNode(x + 1, y));}
      // up
      if (existNode(x, y - 1)) {v->neighbor.push_back(getNode(x, y - 1));}
      // down
      if (existNode(x, y + 1)) {v->neighbor.push_back(getNode(x, y + 1));}
    }
  }
}

bool Grid::existNode(int id) const
{
  return 0 <= id && id < width * height && V[id] != nullptr;
}

bool Grid::existNode(int x, int y) const
{
  return 0 <= x && x < width && 0 <= y && y < height &&
         existNode(y * width + x);
}

Node * Grid::getNode(int id) const {return V[id];}

Node * Grid::getNode(int x, int y) const {return getNode(y * width + x);}
}
