# mapf-IR-ros2
ROS2 wrapper for the mapf-IR library

This ROS2 package wraps the `lib-mapf` library developed by [Kei18](https://github.com/Kei18), but with a few minor changes. This allows the mapf library to be used in ROS2 packages.

The main repositories used include the following **forks** as submodules
1. [mapf-IR](https://github.com/tanjpg/mapf-IR-ros2/tree/main)
2. [grid-pathfinding](https://github.com/tanjpg/grid-pathfinding)

# Installation

```bash
cd $COLCON_WS

cd src

git clone --recursive git@github.com:tanjpg/mapf-IR-ros2.git

cd $COLCON_WS

colcon build

source install/setup.bash

```

# TODOS

Will add example ros2 packages that shows an example of how the library can be used in the future