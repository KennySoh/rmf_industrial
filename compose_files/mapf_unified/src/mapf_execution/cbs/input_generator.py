import argparse
import os
from pathlib import Path

import yaml
import random



def generate_agents(num_agents):
    """Generate a list of agents"""
    agents = []
    for i in range(num_agents):
        start = [i, 0]  
        goal = [i, 0+10]
        agent = {
            'start': start,
            'goal': goal,
            'name': f'agent_{i}'
        }
        agents.append(agent)
    return agents

def generate_obstacles(dimensions, num_obstacles):
    """Generate a list of random obstacle positions."""
    width, height = dimensions
    obstacles = set()
    
    while len(obstacles) < num_obstacles:
        obstacle = (random.randint(0, width - 1), random.randint(0, height - 1))
        obstacles.add(obstacle)
    
    return list(obstacles)

def generate_yaml(num_agents, num_obstacles, map_dimensions):
    """Generate a YAML string."""
    
    obstacles = generate_obstacles(map_dimensions, num_obstacles)
    
    data = {
        'agents': generate_agents(num_agents),
        'map': {
            'dimensions': map_dimensions,
            'obstacles': obstacles
        }
    }
    
    yaml_string = yaml.dump(data, default_flow_style=False, sort_keys=False)
    return yaml_string

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="output file")
    args = parser.parse_args()

    num_agents = 200
    num_obstacles = 0
    map_dimensions = [int(num_agents*1.1), 20]

    # Make sure to modify goals above according to dimensions.

    print(map_dimensions)

    # Generate YAML content
    yaml_content = generate_yaml(num_agents, num_obstacles, map_dimensions)

    file = Path(args.output)
    file.parent.mkdir(parents=True, exist_ok=True)
    # Write YAML content to a file
    with open(args.output, 'w') as file:
        file.write(yaml_content)
    
    print("YAML file generated.")

if __name__ == "__main__":
    main()