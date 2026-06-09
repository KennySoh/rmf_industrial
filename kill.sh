tmux kill-server
psk() {
    echo "$1"
    ps aux | grep $1
    kill -9  $(ps aux | grep -e "$1" | awk '{print $2}')
}
psk vda
docker rm valkey
psk mosquitto
pkill xterm
docker stop $(docker ps -a -q) && docker rm $(docker ps -a -q)
