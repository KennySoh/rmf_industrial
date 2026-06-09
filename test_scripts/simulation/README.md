# Simulation control (MQTT)

Drive the UE5 sim (`RMF2_new_sim`) by hand over the **MQTT broker `localhost:1883`**.

All scripts share one helper, [`lib.py`](lib.py) (a thin `MQTTHelper` class over
`paho-mqtt`, modelled on `test_conveyor_workflow.py`). Install the dependency once:

```bash
pip install paho-mqtt
```

## Quick-start — simple demo

```bash
./demo_single_agv.py            # full pick -> manipulate -> conveyor cycle (serial 10)
./demo_single_agv_reset.py      # put the rack back and park (serial 10)
```

Both take an optional AGV serial: `./demo_single_agv.py 12`.

## Building blocks

```bash
./watch.py                      # watch everything (discovery)
./watch.py asset 1              # watch one device
./watch.py vda 10               # watch one AGV

./send_device.py ManipulatorRobot1 depalletize   # talk to a device
./send_device.py 10 liftrack                      #   (depalletize|dropoff|liftrack|droprack)

./send_agv.py 10 P0             # move an AGV to a waypoint (x,y from the marker grid)
./send_agv.py 10 -30.8 -49.3    # same thing, raw x,y (map frame, metres)
```

Typical use: `./watch.py …` in one terminal, a `send_*` in another.

| Command | Talks to | Topic |
|---------|----------|-------|
| `send_device.py <id> <task_type>` | manipulator / conveyor / rack AMR | `asset/<id>/task_request` |
| `send_agv.py <serial> <Pcode \| x y>` | mobile AGV | `uagv/v2/Manufacturer/<serial>/order` |
| `watch.py [asset\|vda] [id]` | — (listen) | `asset/#`, `uagv/v2/#`, or `#` |

## How it works

`lib.MQTTHelper` keeps a single persistent connection, subscribed up front, with a
background thread buffering every status message — so one-shot completion
events are never missed:

- **moves** block until VDA5050 `/state` reports `lastNodeId == <Pcode>` and not driving;
- **actions** block until `asset/<id>/task_status` reports `COMPLETED`.

Waypoints (`P<idx>`) are converted to map-frame metres with the marker grid in
`lib.py` (`MARKER_ORIGIN_*`, `MARKER_STEP`, `MARKERS_PER_ROW`); per the sim docs
only `task_type` / `task_command` / `asset_id` drive device behaviour.

## Stop

```bash
pkill -f RMF2_new_sim
```
