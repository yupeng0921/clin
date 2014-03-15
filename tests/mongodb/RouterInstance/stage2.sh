#! /bin/bash

log_prefix="mongodb"

function mylog()
{
	logger -t $log_prefix "$1"
	echo "$1"
}

mylog "$*"

declare -a primary_uuids
declare -a primary_hostnames
shared_number=$1
shift 1
for i in `seq 0 $((shared_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	primary_hostnames[$i]=$1
	primary_uuids[$i]=$3
	shift 3
done

secondary_number_per_shared=$1
secondary_number=$(($shared_number * $secondary_number_per_shared))

shift 1

for i in `seq 0 $((secondary_number-1))`; do
	echo "$2 $1" >> /etc/hosts
	shift 2
done

declare -a config_hostnames
config_number=$1
shift 1
for i in `seq 0 $((config_number-1))`; do
	config_hostnames[$i]=$1
	echo "$2 $1" >> /etc/hosts
	shift 2
done

first_router=""
router_number=$1
shift 1
for i in `seq 0 $((router_number-1))`; do
	if [ "$first_router" == "" ]; then
		first_router=$1
	fi
	echo "$2 $1" >> /etc/hosts
	shift 2
done

str="mongos --configdb "

count=0
for i in ${config_hostnames[@]}; do
	count=$((++count))
	if [ "$count" == "$config_number" ]; then
		str="$str""$i"":27019"
	else
		str="$str""$i"":27019,"
	fi
done

str="$str"" --fork --logpath /tmp/mongodblog"

mylog "$str"
$str

my_name=`hostname`
if [ "$my_name" != "$first_router" ]; then
	mylog "not first"
	exit 0
fi

shared_database=$1
shared_collection=$2
shared_key=$3

for i in `seq 0 $((shared_number-1))`; do
	uuid=${primary_uuids[$i]}
	tmp=${uuid//\//}
	rs_name=${tmp//\:/}
	hostname=${primary_hostnames[$i]}
	mylog "rs_name: $rs_name"
	mylog "hostname: $hostname"
	echo "sh.addShard(\"$rs_name/$hostname:27017\")" | mongo
done

mylog "shared_database: $shared_database"
mylog "shared_collection $shared_collection"
mylog "shared_key $shared_key"

echo "sh.enableSharding(\"$shared_database\")" | mongo
echo "sh.shardCollection(\"$shared_database.$shared_collection\", $shared_key)" | mongo
