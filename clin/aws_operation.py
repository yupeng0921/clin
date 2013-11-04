#! /usr/bin/env python

from cloud_operation import CloudOperation
import os
import sys
import time

try:
    import boto.ec2
except ImportError, e:
    load_boto = False
else:
    load_boto = True

class AwsOperation(CloudOperation):
    __name_to_conf = {}
    __name_to_sg = {}
    __uuid_to_instance_id = {}
    def __init__(self, stack_name, conf_dir, only_dump, input_param_dict):
        global load_boto
        if not only_dump and not load_boto:
            sys.stderr.write(u'boto is not install, please install it and this command again\n')
            sys.exit(1)
        self.__stack_name = stack_name
        self.__conf_dir = conf_dir
        self.__only_dump = only_dump
        self.__input_param_dict = input_param_dict

    def get_region(self):
        regions = [u'us-east-1', u'us-west-1', u'us-west-2', \
                       u'eu-west-1', u'ap-southeast-1', u'ap-southeast-2', \
                       u'ap-northeast-1', u'sa-east-1']
        if u'region' in self.__input_param_dict:
            region = self.__input_param_dict[u'region']
            if not region in regions:
                sys.stderr(u'invalid region: %s' % region)
        else:
            while True:
                for region in regions:
                    print(region)
                prompt = u'select a region:'
                region = raw_input(prompt)
                if region in regions:
                    break
        self.__region = region
        if self.__only_dump:
            return
        self.__conn = boto.ec2.connect_to_region(region)
        try:
            self.__key_pair = self.__conn.create_key_pair(self.__stack_name)
        except boto.exception.EC2ResponseError, e:
            sys.stderr.write(u'create keypair failed, maybe stack already exist')
            sys.stderr.write(e)
            sys.exit(1)
        conf_dir = self.__conf_dir
        if not os.path.exists(conf_dir):
            os.mkdir(conf_dir)
        aws_dir = u'%s/aws' % conf_dir
        if not os.path.exists(aws_dir):
            os.mkdir(aws_dir)
        region_dir = u'%s/%s' % (aws_dir, self.__region)
        if not os.path.exists(region_dir):
            os.mkdir(region_dir)
        stack_dir = u'%s/%s' % (region_dir, self.__stack_name)
        if os.path.exists(stack_dir):
            os.rename(stack_dir, u'%s_%s' % (stack_dir, time.time()))
        os.mkdir(dir1)
        self.__key_pair.save(u'%s/key.pem' % dir1)

    def get_instance_configure(self, name):
        pass
    def launch_instance(self, uuid, name, os_name, security_group_rules):
        pass
    def wait_instance(self, uuid):
        pass
    def get_public_ip(self, uuid):
        pass
    def get_private_ip(self, uuid):
        pass
    def terminate_instance(self, uuid):
        pass
    def terminate_all_instances(self):
        pass
