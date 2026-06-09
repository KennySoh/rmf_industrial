#!/bin/bash
#
# Send Preset Tasks Script
# ========================
# This script replicates the dashboard "Send Preset Task" button functionality.
#
# Dashboard button flow (schedule.tsx):
#   1. POST to http://localhost:8083/send_task (Launcher/dashboard_interface.py)
#      -> Runs this script (generate_batch_edit.py + job loader curl)
#   2. POST to http://localhost:8084/send_task (RTO/mock_bt_job_loader)
#   3. Wait 5 seconds
#
# To manually replicate the full button:
#   curl -X POST http://localhost:8083/send_task && \
#   curl -X POST http://localhost:8084/send_task && \
#   sleep 5
#

source ~/ros_industrial_ws/modules/install/setup.bash
source ~/ros_industrial_ws/modules/rts-venv/bin/activate

# Step 1: Send tasks to RTS scheduler (port 8089)
# Order 1 only: 50 loops, every 20 minutes
echo "[rmf2_rts_send_order.sh] Sending tasks to RTS scheduler..."
python3 ~/ros_industrial_ws/modules/src/rmf2_scheduler/demos/rmf2_scheduler_server/script/generate_batch_edit.py \
  --host localhost \
  --port 8089 \
  -o1 50 \
  -o2 50 \
  -o3 50 \
  -o4 50

# Step 2: Trigger mock BT job loader (port 8084)
# Loads XML jobs from final_phase2_mock_jobs/ and sends to Task Orchestrator (port 8080)
echo "[rmf2_rts_send_order.sh] Triggering mock BT job loader..."
curl -s -X POST http://localhost:8084/send_task
echo ""
echo "[rmf2_rts_send_order.sh] Done!"
