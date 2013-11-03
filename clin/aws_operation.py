#! /usr/bin/env python

from cloud_operation import CloudOperation
import os
import sys
import shutil

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
    def __init__(self, stack_name):
        global load_boto
        if not load_boto:
            sys.stderr.write(u'boto is not install, please install it and this command again\n')
            sys.exit(1)
        self.__stack_name = stack_name
    def get_region(self, input_region):
        regions = [u'us-east-1', u'us-west-1', u'us-west-2', \
                       u'eu-west-1', u'ap-southeast-1', u'ap-southeast-2', \
                       u'ap-northeast-1', u'sa-east-1']
        if input_region:
            if input_region in regions:
                region = input_region
            else:
                sys.stderr(u'invalid input_region: %s' % input_region)
        else:
            while True:
                for region in regions:
                    print(region)
                prompt = u'select a region:'
                region = raw_input(prompt)
                if region in regions:
                    break
        self.__region = region
        self.__conn = boto.ec2.connect_to_region(region)
        try:
            self.__key_pair = self.__conn.create_key_pair(self.__stack_name)
        except boto.exception.EC2ResponseError, e:
            sys.stderr.write(u'create keypair failed, maybe stack already exist')
            sys.stderr.write(e)
            sys.exit(1)
        if not os.path.exists(u'~/.clin'):
            os.mkdir(u'~/.clin')
        if not os.path.exists(u'~/.clin/aws'):
            os.mkdir(u'~/.clin/aws')
        dir1 = u'~/.clin/aws/%s' % region
        if not os.path.exists(dir1):
            os.mkdir(dir1)
        dir1 = u'%s/%s' % (dir1, self.__stack_name)
        if os.path.exists(dir1):
            shutil.rmtree(dir1)
        os.mkdir(dir1)
        self.__key_pair.save(u'%s/key.pem' % dir1)

    def get_instance_configure(self, name, param_list):
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

