#! /bin/bash

log_prefix="mongodb"

function mylog()
{
	logger -t $log_prefix $1
	echo "$1"
}

mylog "disable iptables"
iptables -F

mylog "Creating mongodb.repo"
cat > /etc/yum.repos.d/mongodb.repo << EOF
[mongodb]
name=MongoDB Repository
baseurl=http://downloads-distro.mongodb.org/repo/redhat/os/x86_64/
gpgcheck=0
enabled=1
EOF

mylog "Installing mongodb"
yum install -q -y mongo-10gen mongo-10gen-server

exit 0
