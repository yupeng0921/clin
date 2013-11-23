#! /bin/bash

iptables -F

yum install -y httpd
service httpd start
chkconfig httpd on
echo $HOSTNAME > /var/www/html/index.html
