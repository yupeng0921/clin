#! /bin/bash

log_prefix="mongodb"

function mylog()
{
	logger -t $log_prefix $1
	echo "$1"
}

mylog "$*"

mylog "add hosts"

declare -a private_ips
declare -a hostnames

primary_hostname=$1
primary_private_ip=$2
primary_uuid=$3

echo "$primary_private_ip $primary_hostname" >> /etc/hosts

replica_count=$4

shift 4

for i in `seq 0 $((replica_count-1))`; do
	hostnames[$i]=$1
	private_ips[$i]=$2
	echo "$2 $1" >> /etc/hosts
	shift 2
done

config_number=$1
for i in `seq 0 $((config_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

router_number=$1
for i in `seq 0 $((config_nuber-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

echo "127.0.0.1 `hostname`" >> /etc/hosts

tmp=${primary_uuid//\//}
rs_name=${tmp//\:/}

mylog "rs_name: $rs_name"
echo "replSet = $rs_name" >> /etc/mongod.conf

mylog "start mongod"

service mongod start

mylog "rs.initiate"

echo "rs.initiate()" | mongo
sleep 1

res=0
while [ $res -eq 0 ]
do
	res=`echo 'rs.status()' | mongo --quiet | egrep ok | awk '{print $3}'`
	mylog "$res"
	res=${res/,/}
	sleep 1
done

for i in `seq 0 $((replica_count-1))`; do
	ip=${private_ips[$i]}
	echo "rs.add(\"$ip\")" | mongo
done

exit 0
