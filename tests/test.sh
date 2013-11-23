#! /bin/bash

tmpfile="/tmp/.clintest"

stdbuf -i0 -oL ../clin/cloud_parser.py deploy file://test --stack-name test --productor aws --region us-west-2 --configure-file test.conf | tee $tmpfile

output=`tail -n 2 $tmpfile | head -n 1`
if [ "$output" == "Outputs:" ]; then
	ipaddr=`tail -n 1 $tmpfile`
	curl -s $ipaddr | tee $tmpfile
	num=`cat $tmpfile | wc -l`
	if [ $num -eq 10 ]; then
		echo "success"
		echo "clean ..."
		../clin/cloud_parser.py erase --stack-name test --productor aws --region us-west-2
		rm -f $tmpfile
		exit 0
	fi
fi

exit 1
