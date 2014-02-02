#! /bin/bash

total=$1
shift 1
count=0
out="/var/www/html/index.html"
while [ $# -gt 0 ]; do
	uuid=$1
	ip=$2
	echo $uuid >> $out
	curl -s $ip >> $out
	count=$((++count))
	if [ $count -gt $total ]; then
		echo "out of range" 1>&2
		exit 1
	fi
	shift 2
done
