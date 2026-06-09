"""
Integration test to trigger empty plan response from MAPF solver.

This test simulates a real scenario where the solver returns an empty plan,
which should trigger the error handling in executor.py line 180-188.

Run this test against the live system to verify empty plan handling.
"""

import json
import redis
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("empty_plan_test")

# Redis queue name (same as in main.py)
MAPF_TASK_QUEUE_NAME = "mapf_tasks"


def create_conflicting_task_request():
    """
    Creates a task request that will cause the MAPF solver to fail.

    Uses NGSI-LD format with two robots going to same destination.
    This should cause the solver to fail to find a solution.
    """

    # NGSI-LD format task - two robots to same destination P100
    task_message = {
        'type': 'Task',
        'id': 'urn:ngsi-ld:Task:test_empty_plan_conflict:TaskRequest',
        'taskType': {'type': 'Property', 'value': 'amr_ue5'},
        'taskCommand': {'type': 'Property', 'value': 'RESUME'},
        'taskParams': {
            'type': 'Property',
            'value': [
                {'goal_location': 'P100', 'robot_id': 'MiR_0001', 'start_location': 'P70'},
                {'goal_location': 'P100', 'robot_id': 'MiR_0002', 'start_location': 'P539'}  # Same destination!
            ]
        },
        'taskExpectedStart': {'type': 'Property', 'value': '2025-11-03T12:00:00.000Z'},
        'taskExpectedEnd': {'type': 'Property', 'value': ''},
        'taskExpectedDuration': {'type': 'Property', 'value': ''}
    }

    return json.dumps(task_message)


def create_invalid_location_request():
    """
    Creates a task with invalid/non-existent location.
    This should cause KeyError in the solver.
    Uses NGSI-LD format.
    """

    # NGSI-LD format task - invalid destination
    task_message = {
        'type': 'Task',
        'id': 'urn:ngsi-ld:Task:test_invalid_location:TaskRequest',
        'taskType': {'type': 'Property', 'value': 'amr_ue5'},
        'taskCommand': {'type': 'Property', 'value': 'RESUME'},
        'taskParams': {
            'type': 'Property',
            'value': [
                {'goal_location': 'INVALID_NODE_9999', 'robot_id': 'MiR_0001', 'start_location': 'P70'}
            ]
        },
        'taskExpectedStart': {'type': 'Property', 'value': '2025-11-03T12:00:00.000Z'},
        'taskExpectedEnd': {'type': 'Property', 'value': ''},
        'taskExpectedDuration': {'type': 'Property', 'value': ''}
    }

    return json.dumps(task_message)


def push_task_to_redis(redis_client, task_json, test_name):
    """Push a task request to the Redis queue"""
    logger.info(f"\n{'='*60}")
    logger.info(f"TEST: {test_name}")
    logger.info(f"{'='*60}")
    logger.info(f"Pushing task to queue: {task_json}")

    redis_client.lpush(MAPF_TASK_QUEUE_NAME, task_json)
    logger.info("Task pushed successfully")


def monitor_redis_results(redis_client, task_ids, timeout=30):
    """
    Monitor Redis for task status updates.

    Args:
        redis_client: Redis connection
        task_ids: List of task IDs to monitor
        timeout: How long to wait for results (seconds)
    """
    logger.info(f"\nMonitoring task statuses for {timeout} seconds...")
    start_time = time.time()

    results = {}

    while time.time() - start_time < timeout:
        all_found = True

        for task_id in task_ids:
            if task_id not in results:
                # Check for task status
                status = redis_client.get(task_id)
                status_verbose = redis_client.get(f"{task_id}_v")

                if status:
                    status_str = status.decode('utf-8')
                    status_v_str = status_verbose.decode('utf-8') if status_verbose else "N/A"
                    results[task_id] = {
                        'status': status_str,
                        'details': status_v_str,
                        'timestamp': time.time()
                    }
                    logger.info(f"✓ Task {task_id}: {status_str} - {status_v_str}")
                else:
                    all_found = False

        if all_found:
            break

        time.sleep(0.5)

    return results


def test_empty_plan_scenario(redis_host="localhost", redis_port=6379):
    """
    Main test function to trigger and verify empty plan handling.
    """
    logger.info("="*60)
    logger.info("EMPTY PLAN INTEGRATION TEST")
    logger.info("="*60)

    # Connect to Redis
    try:
        r = redis.Redis(host=redis_host, port=redis_port, db=0)
        r.ping()
        logger.info(f"✓ Connected to Redis at {redis_host}:{redis_port}")
    except Exception as e:
        logger.error(f"✗ Failed to connect to Redis: {e}")
        return False

    # Test 1: Conflicting destinations
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Two robots to same destination (should fail)")
    logger.info("="*60)

    task_json = create_conflicting_task_request()
    push_task_to_redis(r, task_json, "Conflicting Destinations")

    # Monitor results - use the NGSI-LD task ID
    task_ids = ["urn:ngsi-ld:Task:test_empty_plan_conflict:TaskRequest"]
    results = monitor_redis_results(r, task_ids, timeout=30)

    # Verify results
    logger.info("\n" + "-"*60)
    logger.info("TEST 1 RESULTS:")
    logger.info("-"*60)

    if len(results) == 1:
        result = results[task_ids[0]]
        if result['status'] == 'FAILED':
            logger.info("✓ SUCCESS: Task marked as FAILED (expected behavior)")
            logger.info("✓ Empty plan scenario handled correctly!")
            logger.info(f"  Details: {result['details']}")
            return True
        else:
            logger.warning(f"⚠ WARNING: Task status is {result['status']}, expected FAILED")
            logger.info(f"  Details: {result['details']}")
    else:
        logger.error(f"✗ FAILURE: Task did not receive status update")

    return False


def test_invalid_location_scenario(redis_host="localhost", redis_port=6379):
    """
    Test invalid location handling.
    """
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Invalid location (should fail with KeyError)")
    logger.info("="*60)

    try:
        r = redis.Redis(host=redis_host, port=redis_port, db=0)
        r.ping()
    except Exception as e:
        logger.error(f"✗ Failed to connect to Redis: {e}")
        return False

    task_json = create_invalid_location_request()
    push_task_to_redis(r, task_json, "Invalid Location")

    task_ids = ["urn:ngsi-ld:Task:test_invalid_location:TaskRequest"]
    results = monitor_redis_results(r, task_ids, timeout=30)

    logger.info("\n" + "-"*60)
    logger.info("TEST 2 RESULTS:")
    logger.info("-"*60)

    if len(results) == 1:
        result = results[task_ids[0]]
        if result['status'] == 'FAILED' and 'invalid location' in result['details'].lower():
            logger.info("✓ SUCCESS: Task marked as FAILED with 'invalid location' message")
            return True
        else:
            logger.warning(f"⚠ Task status: {result['status']} - {result['details']}")

    return False


def cleanup_test_tasks(redis_host="localhost", redis_port=6379):
    """Clean up test task statuses from Redis"""
    try:
        r = redis.Redis(host=redis_host, port=redis_port, db=0)
        test_keys = [
            "urn:ngsi-ld:Task:test_empty_plan_conflict:TaskRequest",
            "urn:ngsi-ld:Task:test_empty_plan_conflict:TaskRequest_v",
            "urn:ngsi-ld:Task:test_invalid_location:TaskRequest",
            "urn:ngsi-ld:Task:test_invalid_location:TaskRequest_v",
        ]
        for key in test_keys:
            r.delete(key)
        logger.info("✓ Cleaned up test task keys from Redis")
    except Exception as e:
        logger.warning(f"Failed to cleanup: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test empty plan handling in adg_executor")
    parser.add_argument("--redis_host", default="localhost", help="Redis host")
    parser.add_argument("--redis_port", type=int, default=6379, help="Redis port")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup test keys only")
    parser.add_argument("--test", choices=["conflicting", "invalid", "all"],
                       default="all", help="Which test to run")

    args = parser.parse_args()

    if args.cleanup:
        cleanup_test_tasks(args.redis_host, args.redis_port)
    else:
        logger.info("\n" + "="*60)
        logger.info("STARTING EMPTY PLAN INTEGRATION TESTS")
        logger.info("="*60)
        logger.info(f"Redis: {args.redis_host}:{args.redis_port}")
        logger.info("="*60 + "\n")

        results = []

        if args.test in ["conflicting", "all"]:
            results.append(("Conflicting Destinations",
                          test_empty_plan_scenario(args.redis_host, args.redis_port)))

        if args.test in ["invalid", "all"]:
            time.sleep(2)  # Give system time between tests
            results.append(("Invalid Location",
                          test_invalid_location_scenario(args.redis_host, args.redis_port)))

        # Summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        for test_name, passed in results:
            status = "✓ PASSED" if passed else "✗ FAILED"
            logger.info(f"{test_name}: {status}")

        passed_count = sum(1 for _, passed in results if passed)
        logger.info(f"\nTotal: {passed_count}/{len(results)} tests passed")
        logger.info("="*60 + "\n")

        # Cleanup
        cleanup_test_tasks(args.redis_host, args.redis_port)
