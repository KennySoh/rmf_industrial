# Asset List — RMF2_new_sim

Full enumeration of controllable assets and their MQTT topics, assembled from the
confirmed examples + `mapf_unified_repo/RACK_AMR_WAYPOINT_ASSIGNMENTS.txt`
(stations) and the 5×5 = 25 rack/AMR grid.

> The authoritative, *right-now* answer is the live bus: run `../watch.sh`
> (subscribes to `#`) while triggering an action. This file is the static reference.

Confidence key:  ✅ confirmed live   🟡 derived from layout (verify with `watch.sh`)

---

## Plane 1 — Device tasks  (`asset/<asset_id>/task_request`)

### Manipulators → `task_type: depalletize`
| Topic | Marker | Conf |
|-------|--------|------|
| `asset/ManipulatorRobot1/task_request` | P501 | ✅ |
| `asset/ManipulatorRobot2/task_request` | P492 | 🟡 |

### Conveyors → `task_type: dropoff`
| Topic | Marker | Conf |
|-------|--------|------|
| `asset/Conveyor1/task_request` | P619 | ✅ |
| `asset/Conveyor2/task_request` | P617 | 🟡 |
| `asset/Conveyor3/task_request` | P615 | 🟡 |

### Rack AMRs (numeric 1–25) → `task_type: liftrack` / `droprack`
Topics `asset/1/task_request` … `asset/25/task_request`
(`asset/1` ✅ confirmed; `2`–`25` 🟡 inferred from the 25-rack grid).

Status feedback for any device: `asset/<asset_id>/asset_status`.

Send a device task:
```bash
../send_device.sh ManipulatorRobot1 depalletize
../send_device.sh Conveyor1 dropoff
../send_device.sh 1 liftrack
../send_device.sh 1 droprack
```

---

## Plane 2 — VDA5050 AGVs  (`uagv/v2/<manufacturer>/<serial>/...`)

Manufacturer `Manufacturer`, serials **2–25** (🟡 from the coord map
`Manufacturer_2 … Manufacturer_25`; serial 25 ✅ confirmed).

Per robot:
| Topic | Direction | Purpose |
|-------|-----------|---------|
| `uagv/v2/Manufacturer/<serial>/order` | you → robot | order (where to go) |
| `uagv/v2/Manufacturer/<serial>/state` | robot → you | pose, driving, last node |
| `uagv/v2/Manufacturer/<serial>/connection` | robot → you | ONLINE / OFFLINE |

```
serials: 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25
```

Send an order:
```bash
../send_agv.sh 25 10.5 5.2
```

---

## task_type reference

| `task_type` | Asset kind | Topic |
|-------------|-----------|-------|
| `depalletize` | manipulator | `asset/ManipulatorRobotN/task_request` |
| `dropoff` | conveyor | `asset/ConveyorN/task_request` |
| `liftrack` / `droprack` | rack AMR | `asset/<n>/task_request` |
| VDA5050 `order` | AGV | `uagv/v2/Manufacturer/<serial>/order` |

The valid `task_type` set is defined by the sim, not broadcast on the bus —
observe a real one with `../watch.sh` while triggering an action.

_Sources: confirmed topics (project chat); `RACK_AMR_WAYPOINT_ASSIGNMENTS.txt`;
`task_orchestrator_repo/location_coord_map_os_res.json`. Verify live with `../watch.sh`._
