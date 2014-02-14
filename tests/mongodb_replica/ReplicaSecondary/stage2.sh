#! /bin/bash

log_prefix="mongodb"

function mylog()
{
	logger -t $log_prefix $1
	echo "$1"
}

mylog "$*"

mylog "add hosts"
primary_hostname=$1
primary_private_ip=$2

echo "$primary_private_ip $primary_hostname" >> /etc/hosts

replica_count=$3

shift 3

for i in `seq 0 $((replica_count-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

echo "127.0.0.1 `hostname`" >> /etc/hosts

mylog "start mongod"

service mongod start

exit 0
