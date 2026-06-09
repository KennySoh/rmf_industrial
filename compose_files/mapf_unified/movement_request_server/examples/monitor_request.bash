while :
do 
  curl -X 'GET'   'http://localhost:8000/mapf/monitor_task?task_id=dummy_task_1&task_id=dummy_task_2'   -H 'accept: application/json'
  echo ""
  curl -X 'GET'   'http://localhost:8000/mapf/monitor_task_verbose?task_id=dummy_task_1&task_id=dummy_task_2'   -H 'accept: application/json'
  echo ""
  echo ""

  sleep 1
done
