#! /bin/bash

log_prefix="mongodb"

function mylog()
{
	logger -t $log_prefix "$1"
	echo "$1"
}

mylog "$*"

shared_number=$1
shift 1
for i in `seq 0 $((shared_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

secondary_number_per_shared=$1
secondary_number=$(($shared_number * $secondary_number_per_shared))

shift 1

for i in `seq 0 $((secondary_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

config_number=$1
shift 1
for i in `seq 0 $((config_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

router_number=$1
shift 1
for i in `seq 0 $((router_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

mkdir -p /data/configdb

touch /tmp/mongodblog
mongod --configsvr --fork --logpath /tmp/mongodblog &

while true; do
	sleep 1
	grep -q 'waiting for connections on port' /tmp/mongodblog
	[ $? -eq 0 ] && break
done

exit 0
