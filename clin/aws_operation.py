#! /usr/bin/env python

# -*- coding: utf-8 -*-

from cloud_operation import CloudOperation
import os
import sys
import time
import types
import yaml
import shutil
import hashlib

try:
    import boto.ec2
    import boto.s3
    from boto.s3.key import Key
except ImportError, e:
    load_boto = False
else:
    load_boto = True

class AwsOperation(CloudOperation):
    __name_to_conf = {}
    __uuid_to_sg = {}
    __uuid_to_instance_id = {}
    __uuid_to_name = {}
    __sg_prefix = u'Security Group for '
    __key_pair = None
    __has_ssh = {}
    __owner_id = None

    def __init__(self, stack_name, conf_dir, only_dump, input_param_dict):
        global load_boto
        if not only_dump and not load_boto:
            raise Exception(u'boto is not install, please install it and this command again\n')
        self.__stack_name = stack_name
        self.__conf_dir = conf_dir
        self.__only_dump = only_dump
        self.__input_param_dict = input_param_dict
        with open(u'%s/data/aws_os_mapping.yml' % os.path.dirname(__file__), u'r') as f:
            self.__os_mapping = yaml.safe_load(f)

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
        self.__key_pair_path = u'%s/%s.pem' % (stack_dir, self.__stack_name)

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
        if uuid not in self.__uuid_to_sg:
            sg = conn.create_security_group(uuid, self.__sg_prefix + self.__stack_name)
            self.__uuid_to_sg[uuid] = sg
        else:
            sg = self.__uuid_to_sg[uuid]

        os_name = os_name.lower()
        os_id = self.__os_mapping[self.__region][os_name]
        instance_type = self.__name_to_conf[name][u'instance_type']
        volume_size = self.__name_to_conf[name][u'volume_size']
        retry = 5
        while retry >= 0:
            try:
                r = conn.run_instances(image_id=os_id, key_name = self.__key_pair.name, \
                                           instance_type=instance_type, security_group_ids = [sg.id])
            except Exception, e:
                time.sleep(1)
            else:
                break
            retry -= 1
        if retry == 0:
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
            conn.authorize_security_group(uuid, ip_protocol = ip_protocol, \
                                              from_port = from_port, to_port = to_port, \
                                              cidr_ip = cidr_ip)

    def wait_instance(self, uuid, timeout):
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
        conn = boto.ec2.connect_to_region(self.__region)
        instance_id = self.__uuid_to_instance_id[uuid]
        r = conn.get_all_instances(instance_ids=[instance_id])
        i = r[0].instances[0]
        return i.ip_address
    def get_private_ip(self, uuid):
        conn = boto.ec2.connect_to_region(self.__region)
        instance_id = self.__uuid_to_instance_id[uuid]
        r = conn.get_all_instances(instance_ids=[instance_id])
        i = r[0].instances[0]
        return i.private_ip_address
    def terminate_instance(self, uuid):
        pass
    def release_all_resources(self):
        conn = boto.ec2.connect_to_region(self.__region)
        filters = {u'tag:Stack':self.__stack_name}
        volume_ids = []
        reservations = conn.get_all_instances(filters = filters)
        owner_id = None
        for r in reservations:
            if not owner_id:
                owner_id = r.owner_id
            i = r.instances[0]
            devs = i.block_device_mapping
            for dev in devs:
                volume_ids.append(devs[dev].volume_id)
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

        for volume_id in volume_ids:
            retry = 5
            while retry > 0:
                try:
                    conn.delete_volume(volume_id)
                except Exception, e:
                    time.sleep(1)
                else:
                    break
                retry -= 1
            if retry == 0:
                conn.delete_volume(volume_id)

        sgs = conn.get_all_security_groups(filters={u'description':self.__sg_prefix + self.__stack_name})
        for sg in sgs:
            for rule in sg.rules:
                for grant in rule.grants:
                    if grant.group_id:
                        sg.revoke(rule.ip_protocol, rule.from_port, rule.to_port, grant.cidr_ip, grant)
                    else:
                        try:
                            sg.revoke(rule.ip_protocol, rule.from_port, rule.to_port, grant.cidr_ip, None)
                        except Exception, e:
                            pass
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

        if owner_id:
            s3_conn = boto.s3.connect_to_region(self.__region)
            md5 = hashlib.md5()
            md5.update(owner_id)
            bucket_name = u'clin.%s.%s' % (self.__region, md5.hexdigest())
            bucket = s3_conn.get_bucket(bucket_name)
            file_list = []
            pem_file = u'%s/%s.pem' % (self.__stack_name, self.__stack_name)
            file_list.append(pem_file)
            for k in bucket.list():
                if k in file_list:
                    k.delete()
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

    def get_login_user(self, uuid):
        return (u'root', self.__key_pair_path)

    def open_ssh(self, uuid):
        conn = boto.ec2.connect_to_region(self.__region)
        sgs=conn.get_all_security_groups(groupnames=uuid)
        for sg in sgs:
            for rule in sg.rules:
                if rule.ip_protocol == u'tcp' and rule.from_port == u'22' and rule.to_port == u'22':
                    for grant in rule.grants:
                        if grant.cidr_ip == u'0.0.0.0/0':
                            self.__has_ssh[uuid] = True
                            return
        self.__has_ssh[uuid] = False
        conn.authorize_security_group(uuid, ip_protocol = u'tcp', \
                                          from_port = u'22', to_port = u'22', \
                                          cidr_ip = u'0.0.0.0/0')
        sgs=conn.get_all_security_groups(groupnames=uuid)
        for sg in sgs:
            if sg.owner_id:
                self.__owner_id = sg.owner_id
                return

    def close_ssh(self, uuid):
        if uuid not in self.__has_ssh:
            raise Exception(u'open ssh not called')
        if self.__has_ssh[uuid]:
            return
        conn = boto.ec2.connect_to_region(self.__region)
        sgs=conn.get_all_security_groups(groupnames=uuid)
        for sg in sgs:
            for rule in sg.rules:
                if rule.ip_protocol == u'tcp' and rule.from_port == u'22' and rule.to_port == u'22':
                    for grant in rule.grants:
                        if grant.cidr_ip == u'0.0.0.0/0':
                            try:
                                sg.revoke(rule.ip_protocol, rule.from_port, rule.to_port, grant.cidr_ip, None)
                            except Exception, e:
                                pass
                            return

    def save_to_remote(self):
        if not self.__owner_id:
            raise Exception(u'no owner id')
        md5 = hashlib.md5()
        md5.update(self.__owner_id)
        bucket_name = u'clin.%s.%s' % (self.__region, md5.hexdigest())
        conn=boto.s3.connect_to_region(self.__region)
        try:
            bucket = conn.create_bucket(bucket_name, location=self.__region)
        except Exception, e:
            bucket = conn.get_bucket(bucket_name)
        else:
            print(u'create new bucket: %s\n' % bucket)
        k = Key(bucket)
        k.key = u'%s/%s.pem' % (self.__stack_name, self.__stack_name)
        k.set_contents_from_filename(self.__key_pair_path)
        os.remove(self.__key_pair_path)
