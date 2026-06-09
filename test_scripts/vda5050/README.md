# VDA5050 master — trigger & observe (MQTT)

Trigger the **VDA5050 master** (`vda5050_fiware_repo`) and watch the **client**
(the UE5 sim `RMF2_new_sim`, or a real AGV) drive. Same style as
[`../simulation`](../simulation). One helper, [`lib.py`](lib.py), over `paho-mqtt`
(+ `requests` for the Scorpio path):

```bash
pip install paho-mqtt requests
```

The pipeline is `MAPF solver → executor → Scorpio → vda5050 master → sim`. You can
inject at any layer — full details, message shapes, and the code trace are in
[`architecture.md`](architecture.md).

## Which script for which layer

| Inject at | Emulating | Script |
|-----------|-----------|--------|
| `POST :8009/mapf/send_task` | a task source (runs MAPF) | `send_mapf_task.py` |
| `CommandMessage` entity (HTTP→Scorpio) | the **MAPF executor's output** | `send_command_scorpio.py` |
| `command_updates` (MQTT) | Scorpio's notification | `send_command.py` |
| `uagv/v2/<mfr>/<serial>/order` (MQTT) | the **master's output** | `send_order.py` |

Layers via the master (`send_mapf_task` / `send_command_scorpio` / `send_command`)
need the AGV **already discovered** — the sim/AGV online and publishing state.

## Quick-start

```bash
# trigger the master, watch the order it emits
./watch.py order 10

# full MAPF pipeline
./send_mapf_task.py Manufacturer_10 P619 P585 P551 P517 P483 P484 P518 P552 P586 P620    # MRS_URL= to override

# act as the MAPF executor (real path through Scorpio)
./send_command_scorpio.py 10 P619 P585 P551 P517 P483 P484 P518 P552 P586 P620     # SCORPIO_URL= to override

# creates a command_updates to the vda5050 master (Mqtt)
./send_command.py 10 P619 P585 P551 P517 P483 P484 P518 P552 P586 P620

# drive the sim directly, vda5050 client (Mqtt)
./send_order.py 10 P619 P585 P551 P517 P483 P484 P518 P552 P586 P620

# canned demos (via the master)
./demo_single_agv.py            # route P123 → P501 → P619
./demo_single_agv_reset.py      # send it home
```

## Watch

```bash
./watch.py                # ALL VDA5050 topics (uagv/#)
./watch.py order 10       # orders the master emits for AGV 10
./watch.py state 10       # state the AGV reports
./watch.py 10             # everything for AGV 10
```

## Files

```
# senders, one per layer (see the table above)
send_mapf_task.py        layer 1 — POST a task to the MAPF movement_request_server
send_command_scorpio.py  layer 2 — HTTP CommandMessage -> Scorpio -> master
send_command.py          layer 3 — fake Scorpio's notification on command_updates
send_order.py            layer 4 — VDA5050 order straight to the sim (no master)
# demos / observe
demo_single_agv.py       drive one AGV through a route via the master
demo_single_agv_reset.py send the AGV back to a home node, via the master
watch.py                 tail topics (order, state, one AGV, or everything)
# shared / docs
lib.py                   MQTTHelper + Scorpio helpers — imported, not run directly
explanation.md           plain-English: the Scorpio command+payload, and why so many scripts
architecture.md          how it all fits + full code trace (file:line)
```

New here? Start with [`explanation.md`](explanation.md).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | `pip install paho-mqtt requests` |
| command sent, no order | AGV not discovered (sim offline?), or `nodeId` not in the master's map — check `./watch.py order <serial>` and the master logs |
| multi-node command emits nothing | no map edge between a consecutive pair — use single-node hops |
| order emitted but AGV idle | the sim/AGV isn't consuming the `order` topic — check it's online |

- **Identity:** default manufacturer `Manufacturer`, serial `10`. `MANUFACTURER`
  lives in `lib.py`; serial is each script's first arg.
- **White-box unit tests** of the master's logic (no broker needed) live in the
  repo: `vda5050_fiware_repo/run_all_tests.py`.
