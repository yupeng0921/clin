#! /usr/bin/env python

import os
import yaml
import time
from profile_ops import generate_profile, verify_profile

try:
    import boto
    import boto.vpc
    import boto.ec2
    import boto.ec2.networkinterface
except Exception, e:
    have_boto = False
else:
    have_boto = True

def get_os_id(os_name, region):
    with open(u'%s/data/aws_os_mapping.yml' % os.path.dirname(__file__), u'r') as f:
        os_mapping = yaml.safe_load(f)
    os_id = os_mapping[region][os_name]
    return os_id

class Driver():
    def get_regions(self):
        if not have_boto:
            raise Exception(u'please install boto: pip install boto')
        regions = [u'us-east-1', u'us-west-1', u'us-west-2', \
                       u'eu-west-1', u'ap-southeast-1', u'ap-southeast-2', \
                       u'ap-northeast-1', u'sa-east-1']
        return regions

    def get_specialisms(self, region):
        conn = boto.vpc.connect_to_region(region)
        vpcs = conn.get_all_vpcs()
        allowed_values = []
        for vpc in vpcs:
            allowed_value = u'%s %s' % (vpc.cidr_block, vpc.id)
            allowed_values.append(allowed_value)
        profile = generate_profile(u'vpc', u'String', u'vpc', allowed_values)
        return [profile]

    def verify_specialisms(self, profiles, region):
        return None

    def get_instance_profiles(self, region, specialisms):
        profiles = []

        profile = generate_profile(u'instance type', u'String', 'instance type', allowed_values=[u't1.micro', u'm1.small'])
        profiles.append(profile)

        profile = generate_profile(u'disk size', u'String', u'disk size', max_value=1000, min_value=8)
        profiles.append(profile)

        profile = generate_profile(u'iops', u'String', u'iops', allowed_values=[u'disable', u'100', u'200', u'400', u'800', u'1000', u'2000', u'4000'])
        profiles.append(profile)

        vpc_id = specialisms[u'vpc'].split(u' ')[1]
        conn = boto.vpc.connect_to_region(region)
        subnets = conn.get_all_subnets(filters=[('vpcId', [vpc_id])])
        allowed_values = []
        for subnet in subnets:
            allowed_value = u'%s %s' % (subnet.cidr_block, subnet.id)
            allowed_values.append(allowed_value)
        profile = generate_profile(u'subnets', u'List', u'subnets', allowed_values)
        profiles.append(profile)

        return profiles

    def verify_instance_profiles(self, profiles, region, specialisms):
        return verify_profile(profiles[0])

    def create_keypair(self, key_name, region):
        conn = boto.ec2.connect_to_region(region)
        key_pair = conn.create_key_pair(key_name)
        key_pair.save(u'./')
        return u'%s.pem' % key_name

    def launch_instance(self, uuid, profiles_dict, \
                            key_name, os_name, region, specialisms, \
                            number):
        conn = boto.ec2.connect_to_region(region)
        vpc_id = specialisms[u'vpc'].split(u' ')[1]
        sg = conn.create_security_group(uuid, u'stack: %s' % key_name, vpc_id=vpc_id)
        os_name = os_name.lower()
        os_id = get_os_id(os_name, region)
        instance_type = profiles_dict[u'instance type']
        disk_size = profiles_dict[u'disk size']
        iops = profiles_dict[u'iops']
        subnets = profiles_dict[u'subnets']
        index = number % len(subnets)
        subnet_id = subnets[index].split(u' ')[1]

        root_dev = boto.ec2.blockdevicemapping.BlockDeviceType(connection=conn, size=disk_size)
        bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping(connection=conn)
        root_name = conn.get_all_images(image_ids=os_id)[0].block_device_mapping.keys()[0]
        bdm[root_name] = root_dev

        interface = boto.ec2.networkinterface.NetworkInterfaceSpecification(subnet_id=subnet_id,
                                                                            groups=[sg.id],
                                                                            associate_public_ip_address=True)
        interfaces = boto.ec2.networkinterface.NetworkInterfaceCollection(interface)
        retry = 10
        while retry > 0:
            try:
                r = conn.run_instances(image_id=os_id, key_name=key_name, \
                                           instance_type=instance_type, \
                                           block_device_map=bdm, \
                                           network_interfaces=interfaces)
            except Exception, e:
                time.sleep(3)
            else:
                break
            retry -= 1
        if retry == 0:
            r = conn.run_instances(image_id=os_id, key_name=key_name, \
                                           instance_type=instance_type, \
                                           block_device_map=bdm, \
                                           network_interfaces=interfaces)
        instance_id = r.instances[0].id
        tags = {}
        tags[u'Name'] = uuid
        tags[u'StackName'] = key_name
        retry = 10
        while retry > 0:
            try:
                conn.create_tags(instance_id, tags)
            except Exception, e:
                time.sleep(3)
            else:
                break
            retry -= 1
        if retry == 0:
            conn.create_tags(instance_id, tags)

    def set_instance_sg(self, uuid, sg_rules, region):
        conn = boto.ec2.connect_to_region(region)
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
            filters={u'group-name': uuid}
            sgs=conn.get_all_security_groups(filters=filters)
            if len(sgs) != 1:
                raise Exception(u'sg count error, %s %s' % (filters, sgs))
            sg = sgs[0]
            sg.authorize(ip_protocol=ip_protocol, from_port=from_port, to_port=to_port, cidr_ip=cidr_ip)

    def get_username(self, uuid, region):
        # FIXME
        return u'root'

    def get_public_ip(self, uuid, region):
        conn = boto.ec2.connect_to_region(region)
        rs = conn.get_all_instances(filters={u'tag:Name':uuid})
        if not rs:
            raise Exception(u'%s not found when get public ip' % uuid)
        r = rs[0]
        i = r.instances[0]
        return i.ip_address

    def get_private_ip(self, uuid, region):
        conn = boto.ec2.connect_to_region(region)
        rs = conn.get_all_instances(filters={u'tag:Name':uuid})
        if not rs:
            raise Exception(u'%s not found when get private ip' % uuid)
        r = rs[0]
        i = r.instances[0]
        return i.private_ip_address

    def get_hostname(self, uuid, region):
        private_ip = self.get_private_ip(uuid, region)
        hostname = u'ip-%s' % private_ip.replace(u'.', u'-', 4)
        return hostname

    def release_all(self, stack_name, region):
        conn = boto.ec2.connect_to_region(region)
        filters = {u'tag:StackName': stack_name}
        volume_ids = []
        reservations = conn.get_all_instances(filters = filters)
        for r in reservations:
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
            retry = 10
            while retry > 0:
                try:
                    conn.delete_volume(volume_id)
                except Exception, e:
                    time.sleep(3)
                else:
                    break
                retry -= 1
            if retry == 0:
                conn.delete_volume(volume_id)

        sgs = conn.get_all_security_groups(filters={u'description': u'stack: %s' % stack_name})
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
            retry = 10
            while retry > 0:
                try:
                    sg.delete()
                except Exception, e:
                    time.sleep(3)
                else:
                    break
                retry -= 1
            if retry == 0:
                sg.delete()

        keys = conn.get_all_key_pairs(keynames=stack_name)
        for k in keys:
            k.delete()

        os.remove(u'%s.pem' % stack_name)

    def wait_for_running(self, uuid, region):
        conn = boto.ec2.connect_to_region(region)
        interval = 5
        timeout = 10*60
        count = 0
        while True:
            rs = conn.get_all_instances(filters={u'tag:Name':uuid})
            if not rs:
                raise Exception(u'%s not found when wait for running' % uuid)
            r = rs[0]
            i = r.instances[0]
            if i.state == u'running':
                return
            elif i.state == u'terminated':
                raise Exception(u'instance terminate, %s %s' % \
                                    (uuid, i.id))
            elif interval * count > timeout:
                raise Exception(u'timeout, %s %s' % \
                                    uuid, i.id)
            time.sleep(interval)
            count += 1

    def open_ssh(self, uuid, region):
        conn = boto.ec2.connect_to_region(region)
        filters={u'group-name': uuid}
        sgs=conn.get_all_security_groups(filters=filters)
        for sg in sgs:
            for rule in sg.rules:
                if rule.ip_protocol == u'tcp' and rule.from_port == u'22' and rule.to_port == u'22':
                    for grant in rule.grants:
                        if grant.cidr_ip == u'0.0.0.0/0':
                            return False
        for sg in sgs:
            sg.authorize(ip_protocol=u'tcp', from_port = u'22', to_port = u'22', cidr_ip = u'0.0.0.0/0')
        return True

    def close_ssh(self, uuid, region, ret):
        if not ret:
            return
        conn = boto.ec2.connect_to_region(region)
        filters={u'group-name': uuid}
        sgs=conn.get_all_security_groups(filters=filters)
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

driver = Driver()
