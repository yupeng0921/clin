#! /usr/bin/env python

# -*- coding: utf-8 -*-

from cloud_operation import CloudOperation
import os
import sys
import time
import types
import yaml
import shutil

try:
    import boto.ec2
except ImportError, e:
    load_boto = False
else:
    load_boto = True

with open(u'aws_os_mapping.yml', u'r') as f:
    os_mapping = yaml.safe_load(f)

class AwsOperation(CloudOperation):
    __name_to_conf = {}
    __name_to_sg = {}
    __uuid_to_instance_id = {}
    __uuid_to_name = {}
    __sg_prefix = u'Security Group for '
    __key_pair = None
    def __init__(self, stack_name, conf_dir, only_dump, input_param_dict):
        global load_boto
        if not only_dump and not load_boto:
            raise Exception(u'boto is not install, please install it and this command again\n')
        self.__stack_name = stack_name
        self.__conf_dir = conf_dir
        self.__only_dump = only_dump
        self.__input_param_dict = input_param_dict

    def get_region(self, input_region):
        regions = [u'us-east-1', u'us-west-1', u'us-west-2', \
                       u'eu-west-1', u'ap-southeast-1', u'ap-southeast-2', \
                       u'ap-northeast-1', u'sa-east-1']
        if input_region:
            region = input_region
            if not region in regions:
                raise Exception(u'invalid region: %s' % region)
        else:
            while True:
                for region in regions:
                    print(region)
                prompt = u'select a region:'
                region = raw_input(prompt)
                if region in regions:
                    break
        self.__region = region
    def __create_keypair(self):
        conn = boto.ec2.connect_to_region(self.__region)
        try:
            self.__key_pair = conn.create_key_pair(self.__stack_name)
        except boto.exception.EC2ResponseError, e:
            raise Exception(u'create keypair failed, maybe stack already exist\n%s', e)
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
        os.mkdir(stack_dir)
        self.__key_pair.save(stack_dir)

    def get_instance_configure(self, name, description):
        instance_types = [u't1.micro', u'm1.small', u'm1.medium', u'm1.large',
                         u'm1.xlarge', u'm3.xlarge', u'm3.2xlarge']
        instance_type = None
        volume_size = None
        if name in self.__input_param_dict:
            if u'instance_type' in self.__input_param_dict[name]:
                instance_type = self.__input_param_dict[name][u'instance_type']
                if not instance_type in instance_types:
                    raise Exception(u'instance_type wrong, %s %s' % \
                                        name, instance_type)
            if u'volume_size' in self.__input_param_dict[name]:
                volume_size = self.__input_param_dict[name][u'volume_size']
                if not type(volume_size) is types.IntType:
                    raise Exception(u'volume_size wrong, %s %s' % \
                                       name, volume_size)
        if (not instance_type) or (not volume_size):
            if description:
                instance_info = description
            else:
                instance_info = name
            print(instance_info)
        if not instance_type:
            while True:
                for instance_type in instance_types:
                    print(instance_type)
                prompt = u'select an instance type:'
                instance_type = raw_input(prompt)
                if instance_type in instance_types:
                    break
        if not volume_size:
            while True:
                prompt = u'default volume size (Gbyte):'
                volume_size = raw_input(prompt)
                try:
                    volume_size = int(volume_size)
                except Exception, e:
                    continue
                else:
                    break
        self.__name_to_conf[name] = {u'instance_type': instance_type, u'volume_size':volume_size}

    def launch_instance(self, uuid, name, os_name):
        if not self.__key_pair:
            self.__create_keypair()
        conn = boto.ec2.connect_to_region(self.__region)
        if name not in self.__name_to_sg:
            sg = conn.create_security_group(name, self.__sg_prefix + self.__stack_name)
            self.__name_to_sg[name] = sg
        else:
            sg = self.__name_to_sg[name]

        os_name = os_name.lower()
        os_id = os_mapping[self.__region][os_name]
        instance_type = self.__name_to_conf[name][u'instance_type']
        volume_size = self.__name_to_conf[name][u'volume_size']
        r = conn.run_instances(image_id=os_id, key_name = self.__key_pair.name, \
                                   instance_type=instance_type, security_group_ids = [sg.id])
        instance_id = r.instances[0].id
        tags = {}
        tags[u'Name'] = uuid
        tags[u'Stack'] = self.__stack_name
        retry = 5
        while retry > 0:
            try:
                conn.create_tags(instance_id, tags)
            except Exception, e:
                time.sleep(1)
            else:
                break
            retry -= 1
        if retry == 0:
            conn.create_tags(instance_id, tags)
        self.__uuid_to_instance_id[uuid] = instance_id
        self.__uuid_to_name[uuid] = name

    def set_instance_sg(self, uuid, sg_rules):
        name = self.__uuid_to_name[uuid]
        conn = boto.ec2.connect_to_region(self.__region)
        for rule in sg_rules:
            [ip_protocol, port, cidr_ip] = rule.split(u' ')
            p = port.split(u'-')
            if len(p) == 1:
                from_port = to_port = int(p[0])
            elif len(p) == 2:
                from_port = int(p[0])
                to_port = int(p[1])
            else:
                raise Exception(u'Invalid rule: %s' % rule)
            retry = 5
            while retry > 0:
                try:
                    conn.authorize_security_group(name, ip_protocol = ip_protocol, \
                                                      from_port = from_port, to_port = to_port, \
                                                      cidr_ip = cidr_ip)
                except Exception, e:
                    time.sleep(1)
                else:
                    break
                retry -= 1
            if retry == 0:
                conn.authorize_security_group(name, ip_protocol = ip_protocol, \
                                                  from_port = from_port, to_port = to_port, \
                                                  cidr_ip = cidr_ip)

    def wait_instance(self, uuid, timeout):
        return
        conn = boto.ec2.connect_to_region(self.__region)
        instance_id = self.__uuid_to_instance_id[uuid]
        interval = 5
        count = 0
        while True:
            r = conn.get_all_instances(instance_ids=[instance_id])
            i = r[0].instances[0]
            if i.state == u'running':
                return True
            elif i.state == u'terminated':
                raise Exception(u'instance terminate, %s %s' % \
                                    uuid, i.id)
            elif (timeout > 0) and (interval * count > timeout):
                return False
            time.sleep(interval)
            count += 1

    def get_public_ip(self, uuid):
        pass
    def get_private_ip(self, uuid):
        pass
    def terminate_instance(self, uuid):
        pass
    def release_all_resources(self):
        conn = boto.ec2.connect_to_region(self.__region)
        filters = {u'tag:Stack':self.__stack_name}
        reservations = conn.get_all_instances(filters = filters)
        for r in reservations:
            i = r.instances[0]
            i.terminate()
        while True:
            reservations = conn.get_all_instances(filters = filters)
            all_terminated = True
            for ins in reservations:
                for i in ins.instances:
                    if i.state != u'terminated':
                        all_terminated = False
            if all_terminated:
                break
            time.sleep(3)

        sgs = conn.get_all_security_groups(filters={u'description':self.__sg_prefix + self.__stack_name})
        for sg in sgs:
            for rule in sg.rules:
                for grant in rule.grants:
                    if grant.group_id:
                        sg.revoke(rule.ip_protocol, rule.from_port, rule.to_port, grant.cidr_ip, grant)
                    else:
                        sg.revoke(rule.ip_protocol, rule.from_port, rule.to_port, grant.cidr_ip, None)
        for sg in sgs:
            retry = 5
            while retry > 0:
                try:
                    sg.delete()
                except Exception, e:
                    time.sleep(1)
                else:
                    break
            retry -= 1
            if retry == 0:
                sg.delete()

        try:
            keys=conn.get_all_key_pairs(keynames=self.__stack_name)
        except Exception, e:
            print(u'get key error')
            print(e)
        else:
            for k in keys:
                k.delete()

        stack_dir = u'%s/aws/%s/%s' % (self.__conf_dir, self.__region, self.__stack_name)
        if os.path.exists(stack_dir):
            shutil.rmtree(stack_dir)

    def return_all_configure(self):
        ret_dict = {}
        for name in self.__name_to_conf:
            ret_dict[name] = self.__name_to_conf[name]
        return ret_dict
