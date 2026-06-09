# VDA5050 master — architecture & code trace

How a movement flows `MAPF → Scorpio → VDA5050 master → sim`, traced through the
real source (file:line), so you can pick a layer and know exactly what to send.

Repos: **`mapf_unified_repo`** (MAPF solver + executor) · **`vda5050_fiware_repo`**
(the master) · **Scorpio** (NGSI-LD context broker) · **`RMF2_new_sim`** / AGV
(the VDA5050 client).

---

## The chain

```
send_mapf_task.py ─POST /mapf/send_task─▶ MRS :8009 ─▶ Redis "mapf_tasks"
                                                          │
                                                  adg_executor (solve + ADG)
                                                          │
              send_command_scorpio.py ─HTTP POST/PATCH─▶  Scorpio :9090
                                          CommandMessage entity
                                                          │  NGSI-LD subscription (type=CommandMessage)
              send_command.py ─MQTT──────────────────▶ command_updates   ◀ Scorpio notifies
                                                          │
                                                   VDA5050 MASTER
                                          convert vs map → VDA5050 order
                                                          │
              send_order.py ─MQTT──────────────▶ uagv/v2/<mfr>/<serial>/order
                                                          │
                                                  RMF2_new_sim / AGV  ── drives
                                                          │ publishes state
                                          uagv/v2/<mfr>/<serial>/state ─▶ master ─▶ Scorpio StateMessage
                                                                                    └▶ executor releases next action
```

**Key point:** the executor never MQTTs the master. It writes a `CommandMessage`
**entity** into Scorpio (HTTP); Scorpio's subscription forwards it to the master
on `command_updates`. That topic is a **Scorpio→master** channel, not an
executor output.

---

## Four layers you can inject at

From highest (most realistic) to lowest (most direct). Each script fakes one hop:

| Inject at | Emulating | Needs running | Script |
|-----------|-----------|---------------|--------|
| `POST :8009/mapf/send_task` | a task source (runs MAPF) | broker+Redis+Scorpio+executor+master+sim | `send_mapf_task.py` |
| `CommandMessage` entity (HTTP→Scorpio) | the **MAPF executor's output** | Scorpio+master(+sim) | `send_command_scorpio.py` |
| `command_updates` (MQTT) | Scorpio's notification | master(+sim) — **no Scorpio** | `send_command.py` |
| `uagv/v2/<mfr>/<serial>/order` (MQTT) | the **master's output** | sim only — **no master** | `send_order.py` |

Layers 3–4 are the fast offline ones. Layer 2 is the faithful "act as MAPF" path.
`watch.py` observes any of them.

---

## Per-hop trace (file:line)

**1. Task in → Redis.** `mapf_unified_repo/movement_request_server/app/main.py:130`
`POST /mapf/send_task` → `r.lpush("mapf_tasks", …)`. Body model
(`app/models.py:12`): `{tasks:[{task_id, robot_id, start_location, goal_location}]}`.

**2. Executor solves + drives.** `mapf_unified_repo/src/mapf_execution/adg_executor/main.py`
dequeues, loads the map from Scorpio (`main.py:40`), calls the solver
(`adg/executor.py:155`), builds the Action Dependency Graph
(`adg/executor.py:227`) and releases actions as deps complete
(`adg/adg_execution.py:109`).

**3. Executor → Scorpio (the real interface).**
`mapf_unified_repo/src/mapf_execution/agents/fiware_agent/utils.py:418` —
`send_entity_message(CommandMessage.to_json("urn:ngsi-ld:CommandMessage:<mfr>:<robot_id>", …))`.
`manufacturer`/`robot_id` are `agent_name.split("_")` (`utils.py:229`).
POST new / PATCH `.../attrs` if it exists (`fiware_api/.../context_broker/scorpio.py:27`).

**4. Scorpio → master.** The master registers the subscription
(`vda5050_fiware_repo/vda5050_fiware/vda5050_fiware/vda5050_fiware.py:100`,
`scorpio.py:214`): `entities=[{type: CommandMessage}]`, notify endpoint
`mqtt://…/command_updates`. Any CommandMessage write → MQTT notification.

**5. Master parses + converts.** `vda5050_fiware.py:125` `on_command_message` →
`conversions.py:82` (mfr/serial = entity id's last two `:`-tokens) →
`conversions.py:32`: each `nodeId` → map node `(x,y)` (`get_node`), connecting
**edges** from the map (`get_edge`; **missing edge ⇒ logged + skipped**,
`conversions.py:45`), sequenceIds nodes `0,2,4…`/edges `1,3,5…`,
`commandId→orderId`, `commandUpdateId→orderUpdateId`. Stitch-guard may queue an
update until the AGV can stitch it (`master.py:411`, `:521`, `:668`).

**6. Order out.** `master.py:1158` publishes to
`uagv/v2/<mfr>/<serial>/order` (`master.py:1180`).

**7. Discovery + feedback.** Master subscribes `uagv/v2/+/+/state` & `…/connection`
(`master.py:902`, `:937`); the first state from an unknown `<mfr>/<serial>`
*discovers* it — **no state ⇒ no order**. Each state is checked for orderId
mismatch (recovery after 3, `master.py:69`,`:613`) and mirrored to Scorpio as
`urn:ngsi-ld:StateMessage:<mfr>:<serial>` (`vda5050_fiware.py:329`). The
executor's StateMessage subscription (`utils.py:338`) releases the next action.

---

## The two command shapes

Same intent, different keys — because Scorpio expands terms the `Link` @context
doesn't define to the `ngsi-ld:default-context/` prefix.

**Layer 2 — CommandMessage entity (HTTP→Scorpio)** plain keys, `Property`
wrappers, `released` as the string `"true"` (`CommandMessage.to_json`):
```json
{"id":"urn:ngsi-ld:CommandMessage:Manufacturer:10","type":"CommandMessage",
 "commandTime":{"type":"Property","value":"2026-06-08T12:34:56.000Z"},
 "command":{"type":"Property","value":"move_to"},
 "commandId":{"type":"Property","value":"cmd_123"},
 "commandUpdateId":{"type":"Property","value":0},
 "waypoints":{"type":"Property","value":[
   {"nodeId":"P123","point2D":{"x":0.0,"y":0.0},"orientation2D":{"theta":0.0},
    "released":"true","sequenceId":0}]}}
```

**Layer 3 — command_updates notification (MQTT→master)** wrapped in
`{"body":{"data":[…]}}`, with `commandTime`/`command`/`waypoints`/`point2D`
prefixed (`CommandMessage.from_subscriber_json`):
```json
{"body":{"data":[{
  "id":"urn:ngsi-ld:CommandMessage:Manufacturer:10","type":"CommandMessage",
  "commandId":{"value":"cmd_123"},"commandUpdateId":{"value":0},
  "ngsi-ld:default-context/commandTime":{"value":"2026-06-08T12:34:56.000Z"},
  "ngsi-ld:default-context/command":{"value":"move_to"},
  "ngsi-ld:default-context/waypoints":{"value":[
    {"nodeId":"P123",
     "ngsi-ld:default-context/point2D":{"ngsi-ld:default-context/x":0.0,
                                        "ngsi-ld:default-context/y":0.0},
     "ngsi-ld:default-context/orientation2D":{"ngsi-ld:default-context/theta":0.0},
     "released":true,"sequenceId":0}]}}]}}
```
`send_command_scorpio.py` emits the first; `send_command.py` emits the second.
The master keys mfr/serial off the entity id's last two tokens, so both
`…:CommandMessage:Manufacturer:10` and the legacy `…:Robot:Manufacturer:10` work.
`point2D` x/y are placeholders — the master uses its own map for coordinates.

---

## Gotchas

- **Discovery first** — the sim/AGV must be online and publishing state, or the
  master drops the order (no such robot).
- **Edges required** — a multi-node command needs a map edge between every
  consecutive pair, else that segment is silently skipped. Real commands are
  single-hop; the demos send one node per step.
- **Timestamp** — the master parses state timestamps strictly as
  `%Y-%m-%dT%H:%M:%S.%fZ` (fractional seconds + `Z`; `state.py:660`).
  `lib.now_iso()` already emits `…S.000Z`.
- **NodeIds** must exist in the master's map (P-codes here exist in both the
  master map and `../simulation/ref/map.yaml`). MAPF's map is
  `warehouse_os_setup_v2` (`mapf_unified_repo/.env`); the master loads its routing
  map from Scorpio by name (default `RMF1`).
- **Identity** — `robot_id` is `<MFR>_<serial>` on the MAPF side; topics/URNs use
  `<mfr>` and `<serial>` separately.

---

## Reference

| Hop | Kind | Address | Source |
|-----|------|---------|--------|
| task in | HTTP POST | `:8009/mapf/send_task` | `movement_request_server/app/main.py:130` |
| command out | HTTP POST/PATCH | `:9090/ngsi-ld/v1/entities[/<id>/attrs]` | `utils.py:418`, `scorpio.py:27` |
| command notify | MQTT | `command_updates` | `vda5050_fiware.py:100`,`:125` |
| order out | MQTT | `uagv/v2/<mfr>/<serial>/order` | `master.py:1158`,`:1180` |
| state in | MQTT | `uagv/v2/+/+/state`, `…/connection` | `master.py:902`,`:937` |
| state mirror | HTTP | `urn:ngsi-ld:StateMessage:<mfr>:<serial>` | `vda5050_fiware.py:329` |

Defaults: broker `localhost:1883`, Scorpio `localhost:9090`, MRS `localhost:8009`.

---

## Recipes

```bash
# Layer 4 — sim only, no master
./send_order.py 10 P123 P501 P619

# Layer 3 — master only, no Scorpio
./send_command.py 10 P123              # then: ./watch.py order 10

# Layer 2 — act as the MAPF executor (real HTTP → Scorpio → master)
./send_command_scorpio.py 10 P123
SCORPIO_URL=http://localhost:9090 ./send_command_scorpio.py 10 P123 P501 P619

# Layer 1 — full MAPF pipeline
./send_mapf_task.py Manufacturer_10 P123 P619
curl "http://localhost:8009/mapf/monitor_task?task_id=<task_id>"

# Observe + demo
./watch.py order 10
./demo_single_agv.py            # route via the master (layer 3)
./demo_single_agv_reset.py      # send it home
```

Layers 1–3 need the AGV already discovered (sim/AGV online and publishing state).
