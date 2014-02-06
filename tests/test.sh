#! /bin/bash

tmpfile="/tmp/.clintest"

if [ "$1" == "" ]; then
	echo "input a stack name"
	exit 1
fi

stack_name="$1"

stdbuf -i0 -oL ../clin/clin_cmd.py deploy file://test --vendor aws --region us-west-2 --configure-file test.yml --stack-name $stack_name | tee $tmpfile

output=`tail -n 2 $tmpfile | head -n 1`
if [ "$output" == "Outputs:" ]; then
	ipaddr=`tail -n 1 $tmpfile`
	curl -s $ipaddr | tee $tmpfile
	num=`cat $tmpfile | wc -l`
	if [ $num -eq 14 ]; then
		echo "success"
		echo "clean ..."
		../clin/clin_cmd.py erase --vendor aws --region us-west-2 --stack-name $stack_name
		rm -f $tmpfile
		exit 0
	fi
fi

exit 1
