#!/usr/bin/env python3
"""
mapf_solver_test.py — exercise the MAPF solver directly and visualize the plan.

This talks straight to the `mapf_solver` HTTP service (port 8888) inside the
`mapf_unified` container. It does NOT need robots, the ADG executor, Redis, or the
UE5 sim — only the solver has to be up. It is therefore the cleanest way to test the
planning core in isolation and to *see* what a collision-free plan looks like.

What it does
------------
1. Parses an RMF map YAML (the same file the solver loads) to get every node's
   (x, y) coordinate and the lane graph.
2. Builds a MAPF request (start/goal per agent, as coordinates) and POSTs it to the
   solver, exactly as `mapf_solve_request.py` does in the repo.
3. Validates the returned plan is genuinely collision-free (no vertex or edge/swap
   conflicts at any timestep) — this is the automated assertion.
4. Renders the result with matplotlib (Agg / headless):
       - <out>/mapf_plan.png  : the graph + each agent's path
       - <out>/mapf_plan.gif  : an animation of the agents executing the plan

Contract (from mapf_unified_repo)
---------------------------------
Request  -> POST http://<host>:8888/
    {
      "mapfile": "warehouse_v2.yaml",
      "solver": "ECBS",
      "max_computation_time": 25000,
      "max_timestep": 1000,
      "tasks": [
        {"agent_name": "r1",
         "start_position": {"x": <cm>, "y": <cm>},
         "end_position":   {"x": <cm>, "y": <cm>}}
      ]
    }
Response <- [ {"agent_name": "r1",
               "steps": [{"step_from": {"node": "P5"},
                          "step_to":   {"node": "P6"},
                          "timestep": 0}, ...]} ]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

try:
    import requests
    import yaml
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e}. Run:  pip install -r requirements.txt")


# --------------------------------------------------------------------------- #
# Map parsing
# --------------------------------------------------------------------------- #
class WarehouseMap:
    """Parsed RMF Traffic-Editor YAML: node coordinates + lane graph."""

    def __init__(self, yaml_path: Path):
        self.path = yaml_path
        self.name = yaml_path.stem
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        levels = data["levels"]
        # The solver hardcodes the "warehouse" level; fall back to the first level.
        level = levels.get("warehouse") or next(iter(levels.values()))

        # vertices: [x, y, z, name, {props}?]   (index in this list == lane id)
        self.coords: dict[str, tuple[float, float]] = {}   # name -> (x, y)
        self.index_to_name: dict[int, str] = {}
        for idx, v in enumerate(level["vertices"]):
            if len(v) < 4 or not v[3]:
                continue  # unnamed vertex; not addressable by name
            name = str(v[3])
            self.coords[name] = (float(v[0]), float(v[1]))
            self.index_to_name[idx] = name

        # lanes: [from_idx, to_idx, {props}?]
        self.edges: list[tuple[str, str]] = []
        navigable_idx: set[int] = set()
        for lane in level.get("lanes", []):
            i, j = int(lane[0]), int(lane[1])
            navigable_idx.update((i, j))
            a, b = self.index_to_name.get(i), self.index_to_name.get(j)
            if a and b:
                self.edges.append((a, b))

        # A node is navigable iff it participates in at least one lane. Vertices with
        # no lane are obstacles in the solver and will be rejected by valid().
        self.navigable: list[str] = [
            self.index_to_name[i] for i in sorted(navigable_idx)
            if i in self.index_to_name
        ]

    def xy(self, node: str) -> tuple[float, float]:
        if node not in self.coords:
            raise KeyError(f"node {node!r} not found in map {self.name}")
        return self.coords[node]


# --------------------------------------------------------------------------- #
# Scenario
# --------------------------------------------------------------------------- #
def parse_task_specs(specs: list[str]) -> list[tuple[str, str, str]]:
    """Each spec is 'agent:START:GOAL'."""
    out = []
    for s in specs:
        parts = s.split(":")
        if len(parts) != 3:
            raise ValueError(f"bad --task {s!r}; expected agent:START:GOAL")
        out.append((parts[0], parts[1], parts[2]))
    return out


def random_scenario(m: WarehouseMap, n: int, seed: int) -> list[tuple[str, str, str]]:
    """Pick n agents with distinct navigable starts and distinct navigable goals."""
    rng = random.Random(seed)
    pool = list(m.navigable)
    if len(pool) < 2 * n:
        raise ValueError(
            f"map has only {len(pool)} navigable nodes; cannot place {n} agents"
        )
    picked = rng.sample(pool, 2 * n)
    starts, goals = picked[:n], picked[n:]
    return [(f"r{i + 1}", starts[i], goals[i]) for i in range(n)]


# --------------------------------------------------------------------------- #
# Solver call
# --------------------------------------------------------------------------- #
def build_request(m: WarehouseMap, tasks, solver, max_comp_ms, max_timestep):
    return {
        "mapfile": m.path.name,
        "solver": solver,
        "max_computation_time": max_comp_ms,
        "max_timestep": max_timestep,
        "tasks": [
            {
                "agent_name": agent,
                "start_position": {"x": m.xy(start)[0], "y": m.xy(start)[1]},
                "end_position": {"x": m.xy(goal)[0], "y": m.xy(goal)[1]},
            }
            for agent, start, goal in tasks
        ],
    }


def call_solver(url: str, payload: dict) -> list[dict]:
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, list):
        raise RuntimeError(f"unexpected solver response (not a list): {body!r}")
    if not body:
        raise RuntimeError(
            "solver returned an empty plan — no solution found "
            "(check that starts/goals are navigable and not duplicated)"
        )
    return body


# --------------------------------------------------------------------------- #
# Plan -> per-agent position timeline
# --------------------------------------------------------------------------- #
def plan_to_timelines(plan: list[dict]) -> dict[str, list[str]]:
    """Return {agent: [node_at_t0, node_at_t1, ...]} padded to common makespan."""
    timelines: dict[str, list[str]] = {}
    for agent_plan in plan:
        agent = agent_plan["agent_name"]
        steps = sorted(agent_plan["steps"], key=lambda s: s["timestep"])
        if not steps:
            continue
        seq = [steps[0]["step_from"]["node"]]
        for s in steps:
            seq.append(s["step_to"]["node"])
        timelines[agent] = seq

    makespan = max((len(s) for s in timelines.values()), default=0)
    for agent, seq in timelines.items():
        if len(seq) < makespan:               # hold final position (robot waits at goal)
            seq.extend([seq[-1]] * (makespan - len(seq)))
    return timelines


def find_conflicts(timelines: dict[str, list[str]]) -> list[str]:
    """Return a list of human-readable conflict descriptions (empty == safe)."""
    conflicts = []
    agents = list(timelines)
    makespan = max((len(s) for s in timelines.values()), default=0)
    for t in range(makespan):
        for ai in range(len(agents)):
            for aj in range(ai + 1, len(agents)):
                a, b = agents[ai], agents[aj]
                pa, pb = timelines[a][t], timelines[b][t]
                if pa == pb:
                    conflicts.append(f"vertex conflict: {a} & {b} both at {pa} @ t={t}")
                if t + 1 < makespan:
                    if timelines[a][t + 1] == pb and timelines[b][t + 1] == pa:
                        conflicts.append(
                            f"edge/swap conflict: {a}({pa}<->{pb}){b} @ t={t}->{t + 1}"
                        )
    return conflicts


# --------------------------------------------------------------------------- #
# Visualization
# --------------------------------------------------------------------------- #
def visualize(m: WarehouseMap, tasks, timelines, out_dir: Path, fps: int):
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    out_dir.mkdir(parents=True, exist_ok=True)
    cmap = plt.get_cmap("tab10")
    colors = {agent: cmap(i % 10) for i, (agent, _, _) in enumerate(tasks)}

    def draw_graph(ax):
        for a, b in m.edges:
            (x1, y1), (x2, y2) = m.xy(a), m.xy(b)
            ax.plot([x1, x2], [y1, y2], color="0.85", lw=0.6, zorder=1)
        xs = [c[0] for c in m.coords.values()]
        ys = [c[1] for c in m.coords.values()]
        ax.scatter(xs, ys, s=4, color="0.6", zorder=2)
        ax.set_aspect("equal")
        ax.set_title(f"MAPF plan — {m.name}")

    # ---- static PNG: graph + full paths ---------------------------------- #
    fig, ax = plt.subplots(figsize=(11, 9))
    draw_graph(ax)
    for agent, start, goal in tasks:
        seq = timelines[agent]
        pts = [m.xy(n) for n in seq]
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                color=colors[agent], lw=2, alpha=0.8, zorder=3, label=agent)
        sx, sy = m.xy(start)
        gx, gy = m.xy(goal)
        ax.scatter([sx], [sy], color=colors[agent], marker="o", s=90,
                   edgecolor="k", zorder=4)
        ax.scatter([gx], [gy], color=colors[agent], marker="*", s=240,
                   edgecolor="k", zorder=4)
    ax.legend(loc="upper right", fontsize=8)
    png = out_dir / "mapf_plan.png"
    fig.savefig(png, dpi=130, bbox_inches="tight")
    plt.close(fig)

    # ---- animated GIF: agents moving over timesteps ---------------------- #
    makespan = max(len(s) for s in timelines.values())
    sub = 6  # interpolation frames between timesteps for smooth motion
    fig, ax = plt.subplots(figsize=(11, 9))
    draw_graph(ax)
    # faint goal markers for reference
    for agent, start, goal in tasks:
        gx, gy = m.xy(goal)
        ax.scatter([gx], [gy], color=colors[agent], marker="*", s=200,
                   edgecolor="k", alpha=0.4, zorder=3)
    dots = {
        agent: ax.scatter([], [], color=colors[agent], s=140,
                          edgecolor="k", zorder=5, label=agent)
        for agent, _, _ in tasks
    }
    label = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top",
                    fontsize=10, family="monospace")
    ax.legend(loc="upper right", fontsize=8)

    total_frames = (makespan - 1) * sub + 1

    def frame(f):
        t = f // sub
        frac = (f % sub) / sub
        t_next = min(t + 1, makespan - 1)
        for agent in timelines:
            (x1, y1) = m.xy(timelines[agent][t])
            (x2, y2) = m.xy(timelines[agent][t_next])
            x = x1 + (x2 - x1) * frac
            y = y1 + (y2 - y1) * frac
            dots[agent].set_offsets([[x, y]])
        label.set_text(f"timestep {t}/{makespan - 1}")
        return list(dots.values()) + [label]

    anim = FuncAnimation(fig, frame, frames=total_frames, blit=True, interval=1000 / fps)
    gif = out_dir / "mapf_plan.gif"
    anim.save(gif, writer=PillowWriter(fps=fps))
    plt.close(fig)

    return png, gif


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def default_map_path() -> Path:
    # test_scripts/mapf/ -> repo root is ../../.. then into mapf_unified_repo
    here = Path(__file__).resolve()
    ws = here.parents[3]  # ros_industrial_ws
    return (ws / "mapf_unified_repo/src/mapf/mapf_service/mapf_service/"
                 "maps/warehouse_v2.yaml")


def main():
    p = argparse.ArgumentParser(
        description="Test the MAPF solver (:8888) directly and visualize the plan.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--map", type=Path, default=default_map_path(),
                   help="RMF map YAML (must also exist by this filename in the container)")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8888)
    p.add_argument("--solver", default="ECBS",
                   help="ECBS | CBS | ICBS | PIBT | PIBT_COMPLETE | HCA | WHCA | IR")
    p.add_argument("--max-comp-ms", type=int, default=25000)
    p.add_argument("--max-timestep", type=int, default=1000)
    p.add_argument("--task", action="append", default=[], metavar="AGENT:START:GOAL",
                   help="explicit task; repeatable. Overrides --random")
    p.add_argument("--random", type=int, default=3, metavar="N",
                   help="auto-generate N agents on random navigable nodes")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "out")
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--no-viz", action="store_true", help="skip PNG/GIF rendering")
    args = p.parse_args()

    if not args.map.exists():
        sys.exit(f"map not found: {args.map}\n"
                 f"Pass --map or check the mapf_unified_repo path.")

    print(f"[map]    {args.map}")
    m = WarehouseMap(args.map)
    print(f"[map]    {len(m.coords)} nodes, {len(m.edges)} lanes, "
          f"{len(m.navigable)} navigable")

    # scenario
    if args.task:
        tasks = parse_task_specs(args.task)
    else:
        tasks = random_scenario(m, args.random, args.seed)
    print("[tasks]  " + ", ".join(f"{a}:{s}->{g}" for a, s, g in tasks))

    # validate node names up front for a friendly error
    for a, s, g in tasks:
        for node in (s, g):
            if node not in m.coords:
                sys.exit(f"node {node!r} (agent {a}) not in map {m.name}")
            if node not in m.navigable:
                print(f"[warn]   {node} is not on any lane (obstacle) — "
                      f"solver will likely reject it")

    url = f"http://{args.host}:{args.port}/"
    payload = build_request(m, tasks, args.solver, args.max_comp_ms, args.max_timestep)
    print(f"[solver] POST {url}  ({args.solver})")
    try:
        plan = call_solver(url, payload)
    except requests.exceptions.ConnectionError:
        sys.exit(f"could not reach solver at {url}\n"
                 f"Is the mapf_unified container up?  "
                 f"curl -s {url} >/dev/null && echo up")
    except Exception as e:
        sys.exit(f"solver error: {e}")

    timelines = plan_to_timelines(plan)
    makespan = max(len(s) for s in timelines.values()) - 1
    print(f"[plan]   {len(timelines)} agents, makespan={makespan}")
    for agent in timelines:
        moves = sum(
            1 for i in range(len(timelines[agent]) - 1)
            if timelines[agent][i] != timelines[agent][i + 1]
        )
        print(f"           {agent}: {moves} moves  "
              f"{timelines[agent][0]} -> {timelines[agent][-1]}")

    # ---- the actual test assertion -------------------------------------- #
    conflicts = find_conflicts(timelines)
    if conflicts:
        print(f"[FAIL]   {len(conflicts)} conflict(s) in solver output:")
        for c in conflicts[:10]:
            print(f"           {c}")
        sys.exit(1)
    print("[PASS]   plan is collision-free (no vertex or edge/swap conflicts)")

    # ---- visualization --------------------------------------------------- #
    if not args.no_viz:
        try:
            png, gif = visualize(m, tasks, timelines, args.out, args.fps)
            print(f"[viz]    {png}")
            print(f"[viz]    {gif}")
        except ImportError as e:
            print(f"[viz]    skipped (missing dependency: {e})")

    print("[done]")


if __name__ == "__main__":
    main()
