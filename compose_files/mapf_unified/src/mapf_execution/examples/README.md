# Examples

These examples run with robots in simulation. The MAPF solver used is the local one in cbs.
Navigate to the directory where this repository was cloned.

## PyBullet examples
Run the mapf_pybullet PyBullet simulations in a separate terminal:

1. Add the mapf_pybullet repository to your Python path
```
source env/bin/activate
PATH_TO_REPO="path/to/mapf_pybullet"
export PYTHONPATH="${PYTHONPATH}:${PATH_TO_REPO}";
```

2. Pass the path of the globalplan file as an argument when running the simulation. This tells the simulation where to spawn the robots.

3. Optionally pass the path of your building file with `--building`

4. Press the Escape key to exit the simulation. 


### Examples


#### 01
Moves four robots in PyBullet according to the input plan in 4_robots.yaml. This example doesn't use the Executor interface.
```
python3 -m examples.example_01_4_robots.main
python3 -m mapf_pybullet.simulation.simulation examples/example_01_4_robots/4_robots.yaml --show-labels
```

#### 02
Moves four robots in PyBullet and triggers replanning.
```
python3 -m examples.example_02_4_robots_replanning.main
python3 -m mapf_pybullet.simulation.simulation examples/example_02_4_robots_replanning/4_robots_replan.yaml --show-labels
```
#### 03

Four robots with more replanning.
```
python3 -m examples.example_03_replanning.main &
python3 -m mapf_pybullet.simulation.simulation examples/example_03_replanning/4_robots.yaml --show-labels
```

#### 04
Tests consecutive and immediate replans.


#### 05
Tests using obstacles to keep robots in place when replanning.  
Uses the mapf solver service (ros2 run mapf run_mapf_service) and a building.yaml file.

#### 06
Tests using obstacles to keep robots in place when replanning.  
Uses the provided CBS solver and the default small grid.
