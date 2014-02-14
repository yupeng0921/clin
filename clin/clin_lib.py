#! /usr/bin/env python

import os
import types
import yaml
import threading
import paramiko
import scp
import time
from jinja2 import Template, Environment, FileSystemLoader
from profile_ops import generate_profile, verify_profile

vendor_dict = {}
import aws_driver
vendor_dict[u'aws'] = aws_driver.driver

def get_vendors():
    return [u'aws']

def get_regions(vendor):
    driver = vendor_dict[vendor]
    return driver.get_regions()

def get_specialisms(vendor, region):
    driver = vendor_dict[vendor]
    return driver.get_specialisms(region)

def verify_specialisms(profiles, vendor, region):
    driver = vendor_dict[vendor]
    return driver.verify_specialisms(profiles, region)

def get_instance_profiles(vendor, region, specialisms):
    driver = vendor_dict[vendor]
    return driver.get_instance_profiles(region, specialisms)

def verify_instance_profiles(profiles, vendor, region, specialisms):
    driver = vendor_dict[vendor]
    return driver.verify_instance_profiles(profiles, region, specialisms)

def create_keypair(keypair_name, vendor, region):
    driver = vendor_dict[vendor]
    return driver.create_keypair(keypair_name, region)

def launch_instance(uuid, profiles, keypair_name, os_name, vendor, region, specialisms, number):
    driver = vendor_dict[vendor]
    return driver.launch_instance(uuid, profiles, keypair_name, os_name, region, specialisms, number)

def set_instance_sg(uuid, sg_rules, vendor, region):
    driver = vendor_dict[vendor]
    return driver.set_instance_sg(uuid, sg_rules, region)

def get_username(uuid, vendor, region):
    driver = vendor_dict[vendor]
    return driver.get_username(uuid, region)

def get_public_ip(uuid, vendor, region):
    driver = vendor_dict[vendor]
    return driver.get_public_ip(uuid, region)

def get_private_ip(uuid, vendor, region):
    driver = vendor_dict[vendor]
    return driver.get_private_ip(uuid, region)

def get_hostname(uuid, vendor, region):
    driver = vendor_dict[vendor]
    return driver.get_hostname(uuid, region)

def wait_for_running(uuid, vendor, region):
    driver = vendor_dict[vendor]
    return driver.wait_for_running(uuid, region)

def open_ssh(uuid, vendor, region):
    driver = vendor_dict[vendor]
    return driver.open_ssh(uuid, region)

def close_ssh(uuid, vendor, region, ret):
    driver = vendor_dict[vendor]
    return driver.close_ssh(uuid, region, ret)

class Instance():
    def __init__(self, uuid):
        attrs = [u'private_ip', u'public_ip', u'uuid', u'hostname']
        for attr in attrs:
            self.__dict__[attr] = u'$$%s.%s$$' % (uuid, attr)

class InstanceInit(threading.Thread):
    def __init__(self, uuid, service_dir, instance_name, hostname, username, key_filename, \
                     deps, init_parameters, vendor, region, \
                     lock_before_init, lock_on_init, lock_after_init, \
                     before_init, on_init, after_init, \
                     send_message, set_complete):
        self.uuid = uuid
        self.service_dir = service_dir
        self.instance_name = instance_name
        self.hostname = hostname
        self.username = username
        self.key_filename = key_filename
        self.deps = deps
        self.init_parameters = init_parameters
        self.vendor = vendor
        self.region = region
        self.lock_before_init = lock_before_init
        self.lock_on_init = lock_on_init
        self.lock_after_init = lock_after_init
        self.before_init = before_init
        self.on_init = on_init
        self.after_init = after_init
        self.send_message = send_message
        self.set_complete = set_complete
        self._running = True
        threading.Thread.__init__(self, name=uuid)

    def run(self):
        hostname = self.hostname
        username = self.username
        vendor = self.vendor
        region = self.region
        uuid = self.uuid
        key_filename = self.key_filename
        service_dir = self.service_dir
        instance_name = self.instance_name
        deps = self.deps
        lock_before_init = self.lock_before_init
        lock_on_init = self.lock_on_init
        lock_after_init = self.lock_after_init
        before_init = self.before_init
        on_init = self.on_init
        after_init = self.after_init
        init_parameters = self.init_parameters
        send_message = self.send_message
        set_complete = self.set_complete

        send_message(u'%s: waiting for running' % uuid)
        wait_for_running(uuid, vendor, region)

        send_message(u'%s: connecting ssh' % uuid)

        ssh_ret = open_ssh(uuid, vendor, region)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        retry = 200
        while retry > 0:
            try:
                ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
            except Exception, e:
                time.sleep(3)
            else:
                break
            retry -= 1
        if retry == 0:
            ssh.connect(hostname=hostname, username=username, key_filename=key_filename)

        send_message(u'%s: copying data' % uuid)
        src = u'%s/%s' % (service_dir, instance_name)
        dst = u'~/'
        scopy = scp.SCPClient(ssh.get_transport())
        scopy.put(src, dst, True)
        ssh.close()

        send_message(u'%s: doing stage1' % uuid)
        cmd = u'bash ~/%s/stage1.sh' % instance_name
        if username != u'root':
            cmd = u'sudo %s' % cmd
        ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
        (stdin, stdout, stderr) = ssh.exec_command(cmd, timeout=6000)
        ret = stdout.read()
        send_message(u'%s stage1 stdout: %s' % (uuid, ret))
        ret = stderr.read()
        send_message(u'%s stage1 stderr: %s' % (uuid, ret))
        stdout.close()
        stderr.close()
        ssh.close()

        if deps:
            send_message(u'%s: waiting deps' % uuid)
            while True:
                lock_after_init.acquire(True)
                can_init = True
                for dep in deps:
                    if dep not in after_init:
                        can_init = False
                        break
                lock_after_init.release()
                if can_init:
                    break
                else:
                    if not self._running:
                        send_message(u'%s: stop' % uuid)
                        return
                    time.sleep(1)

        lock_before_init.acquire(True)
        lock_on_init.acquire(True)
        before_init.remove(uuid)
        on_init.append(uuid)
        lock_on_init.release()
        lock_before_init.release()

        send_message(u'%s: doing state2' % uuid)
        cmd = u'bash ~/%s/stage2.sh' % instance_name
        if username != u'root':
            cmd = u'sudo %s' % cmd
        for p in init_parameters:
            cmd = u'%s %s' % (cmd, p)
        ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
        (stdin, stdout, stderr) = ssh.exec_command(cmd, timeout=6000)
        ret = stdout.read()
        send_message(u'%s stage2 stdout: %s' % (uuid, ret))
        ret = stderr.read()
        send_message(u'%s stage2 stderr: %s' % (uuid, ret))
        stdout.close()
        stderr.close()
        ssh.close()

        close_ssh(uuid, vendor, region, ssh_ret)

        lock_before_init.acquire(True)
        lock_on_init.acquire(True)
        lock_after_init.acquire(True)

        on_init.remove(uuid)
        after_init.append(uuid)

        if not before_init and not on_init:
            set_complete()

        lock_after_init.release()
        lock_on_init.release()
        lock_before_init.release()

        send_message(u'%s: done' % uuid)

    def stop(self):
        self._running = False

class Deploy():
    def __init__(self, service_dir, stack_name, vendor, region, \
                     configure_file, use_compile, \
                     clin_default_dir):
        self.service_dir = service_dir
        self.stack_name = stack_name
        self.vendor = vendor
        self.region = region
        if configure_file:
            with open(configure_file, u'r') as f:
                self.configure_dict = yaml.safe_load(f)
        else:
            self.configure_dict = {}
        self.use_compile = use_compile
        self.clin_default_dir = clin_default_dir
        self.stage = u'init'
        self.conf_dict = {}
        self.conf_dict[u'Parameters'] = {}
        self.conf_dict[u'Specialisms'] = {}
        self.conf_dict[u'Instances'] = {}
        self.parameters_stack = []
        self.instances_stack = []
        self.resources_template = None
        self.all_messages = []
        self.new_messages = []
        self.message_lock = threading.Lock()
        self.deploy_complete = False
        self.instance_dict = {}
        self._load_parameters()
    def get_next(self):
        while True:
            if self.stage == u'init':
                self.stage = u'vendor'
                continue
            elif self.stage == u'vendor':
                allowed_values = get_vendors()
                profile = generate_profile(u'Vendor', u'String', u'Vendor', allowed_values)
                if self.vendor:
                    profile[u'Value'] = self.vendor
                    ret = verify_profile(profile)
                    if ret:
                        raise Exception(ret)
                    self.stage = u'Region'
                    continue
                else:
                    self.stage = u'getting_vendor'
                    return [profile]
            elif self.stage == u'Region':
                vendor = self.vendor
                allowed_values = get_regions(vendor)
                profile = generate_profile(u'Region', u'String', u'Region', allowed_values)
                if self.region:
                    profile[u'Value'] = self.region
                    ret = verify_profile(profile)
                    if ret:
                        raise Exception(ret)
                    self.stage = u'parameters'
                    continue
                else:
                    self.stage = u'getting_region'
                    return [profile]
            elif self.stage == u'parameters':
                if self.parameters_stack:
                    profile = self.parameters_stack.pop()
                    name = profile[u'Name']
                    if self.configure_dict and \
                            u'Parameters' in self.configure_dict and \
                            name in self.configure_dict[u'Parameters']:
                        profile[u'Value'] = self.configure_dict[u'Parameters'][name]
                        ret = verify_profile(profile)
                        if ret:
                            raise Exception(ret)
                        if profile[u'Type'] == u'ParameterGroup' and not profile[u'Value']:
                            for i in range(0, profile[u'SubNumber']):
                                self.parameters_stack.pop()
                        self.conf_dict[u'Parameters'][name] = profile[u'Value']
                        continue
                    else:
                        self.stage = u'getting_parameter'
                        return [profile]
                else:
                    self._load_resources()
                    self.stage = u'specialisms'
                    continue
            elif self.stage == u'specialisms':
                 vendor = self.vendor
                 region = self.region
                 profiles = get_specialisms(vendor, region)
                 if profiles:
                     if u'Specialisms' in self.configure_dict and \
                             self.configure_dict[u'Specialisms']:
                         for profile in profiles:
                             name = profile['Name']
                             if name in self.configure_dict[u'Specialisms']:
                                 profile[u'Value'] = self.configure_dict[u'Specialisms'][name]
                             else:
                                 raise Exception(u'no %s in configure file' % name)
                         ret = verify_specialisms(profiles, vendor, region)
                         if ret:
                             raise Exception(ret)
                         else:
                             for profile in profiles:
                                 name = profile[u'Name']
                                 value = profile[u'Value']
                                 self.conf_dict[u'Specialisms'][name] = value
                             self.stage = u'instances'
                             continue
                     else:
                         self.stage = u'getting_specialisms'
                         return profiles
                 else:
                     self.stage = u'instances'
                     continue
            elif self.stage == u'instances':
                if self.instances_stack:
                    instance_name = self.instances_stack.pop()
                    vendor = self.vendor
                    region = self.region
                    specialisms = self.conf_dict[u'Specialisms']
                    profiles = get_instance_profiles(vendor, region, specialisms)
                    for profile in profiles:
                        profile[u'Name'] = u'%s %s' % (instance_name, profile[u'Name'])
                    if self.configure_dict and \
                            u'Instances' in self.configure_dict and \
                            instance_name in self.configure_dict[u'Instances']:
                        for profile in profiles:
                            name = profile[u'Name']
                            if name in self.configure_dict[u'Instances'][instance_name]:
                                profile[u'Value'] = self.configure_dict[u'Instances'][instance_name][name]
                            else:
                                raise Exception(u'no %s in configure file' % name)
                        ret = verify_instance_profiles(profiles, vendor, region, specialisms)
                        if ret:
                            raise Exception(ret)
                        else:
                            self.conf_dict[u'Instances'][instance_name] = {}
                            for profile in profiles:
                                name = profile[u'Name']
                                value = profile[u'Value']
                                self.conf_dict[u'Instances'][instance_name][name] = value
                            stage = u'instances'
                    else:
                        self.instance_name = instance_name
                        self.stage = u'getting_instances'
                        return profiles
                else:
                    self.stage = u'getting_end'
                    return None
            else:
                raise Exception(self.stage)

    def set_profiles(self, profiles):
        if self.stage == u'getting_vendor':
            profile = profiles[0]
            ret = verify_profile(profile)
            if ret:
                return ret
            self.vendor = profile[u'Value']
            self.stage = u'Region'
            return None
        elif self.stage == u'getting_region':
            vendor = self.vendor
            profile = profiles[0]
            ret = verify_profile(profile)
            if ret:
                return ret
            self.region = profile[u'Value']
            self.stage = u'parameters'
            return None
        elif self.stage == u'getting_parameter':
            profile = profiles[0]
            ret = verify_profile(profile)
            if ret:
                return ret
            if profile[u'Type'] == u'ParameterGroup' and not profile[u'Value']:
                for i in ragne(0, profile[u'SubNumber']):
                    self.parameters_stack.pop()
            name = profile[u'Name']
            self.conf_dict[u'Parameters'][name] = profile[u'Value']
            self.stage = u'parameters'
            return None
        elif self.stage == u'getting_specialisms':
            vendor = self.vendor
            region = self.region
            ret = verify_specialisms(profiles, vendor, region)
            if ret:
                return ret
            else:
                for profile in profiles:
                    name = profile[u'Name']
                    value = profile[u'Value']
                    self.conf_dict[u'Specialisms'][name] = value
                self.stage = u'instances'
                return None
        elif self.stage == u'getting_instances':
            vendor = self.vendor
            region = self.region
            specialisms = self.conf_dict[u'Specialisms']
            ret = verify_instance_profiles(profiles, vendor, region, specialisms)
            if ret:
                return ret
            else:
                profile = profiles[0]
                name = profile[u'Name']
                pos =name.index(' ')
                instance_name = name[0:pos]
                self.conf_dict[u'Instances'][instance_name] = {}
                for profile in profiles:
                    name = profile[u'Name']
                    value = profile[u'Value']
                    self.conf_dict[u'Instances'][self.instance_name][name] = value
                self.stage = u'instances'
                return None
        else:
            raise Exception(u'invalid stage: %s' % self.stage)

    def get_configure(self):
        return self.conf_dict

    def launch_resources(self):
        if not self.resources_template:
            raise Exception(u'not load resources template')
        if self.resources_template and u'Resources' in self.resources_template:
            vendor = self.vendor
            region = self.region
            key_filename = create_keypair(self.stack_name, vendor, region)
            self.key_filename = key_filename
            self._launch_resources(self.resources_template[u'Resources'], self.stack_name)
            self.instance_dict = dict(self.instance_dict, **self.conf_dict[u'Parameters'])
            loader = FileSystemLoader(self.service_dir)
            self.env = Environment(loader = loader)
            self.lock_before_init = threading.Lock()
            self.lock_on_init = threading.Lock()
            self.lock_after_init = threading.Lock()
            self.before_init = []
            self.on_init = []
            self.after_init = []
            self.instance_init_list = []
            self._init_instances(self.resources_template[u'Resources'], self.stack_name)

    def get_all_messages(self):
        messages = []
        self.message_lock.acquire(True)
        for message in self.all_messages:
            messages.append(message)
        self.message_lock.release()
        return messages

    def get_new_messages(self):
        messages = []
        self.message_lock.acquire(True)
        while self.new_messages:
            messages.append(self.new_messages.pop(0))
        self.message_lock.release()
        return messages

    def send_message(self, message):
        self.message_lock.acquire(True)
        self.new_messages.append(message)
        self.all_messages.append(message)
        self.message_lock.release()

    def set_complete(self):
        self.deploy_complete = True

    def is_complete(self):
        return self.deploy_complete

    def get_output(self):
        if not self.deploy_complete:
            raise Exception(u'not complete')
        with open(u'%s/init.yml' % self.service_dir, u'r') as f:
            start_flag = False
            o = u'Outputs'
            outputs_string = u''
            for line in f:
                if line[0:len(o)] == o:
                    start_flag = True
                if start_flag:
                    outputs_string = u'%s%s' % (outputs_string, line)
        t = Template(outputs_string)
        if self.conf_dict and u'Parameters' in self.conf_dict:
            parameters_dict = self.conf_dict[u'Parameters']
        else:
            parameters_dict = {}
        parameters_dict = dict(parameters_dict, **self.instance_dict)
        after_render = t.render(parameters_dict)
        outputs_template = yaml.safe_load(after_render)
        output_list = []
        if outputs_template and u'Outputs' in outputs_template:
            self.current_position = u'%s/&&&&&&&&' % self.stack_name
            outputs = outputs_template[u'Outputs']
            if outputs:
                for item in outputs:
                    real_item = self._explain(item)
                    if real_item:
                        output_list.append(real_item)
        return output_list

    def _load_parameters(self):
        parameters_string = u''
        with open(u'%s/init.yml' % self.service_dir, u'r') as f:
            start_flag = False
            p = u'Parameters'
            r = u'Resources'
            o = u'Outputs'
            for line in f:
                if line[0:len(p)] == p:
                    start_flag = True
                elif line[0:len(r)] == r:
                    break
                elif line[0:len(o)] == o:
                    break
                if start_flag:
                    parameters_string = u'%s%s' % (parameters_string, line)
        parameters_template = yaml.safe_load(parameters_string)
        if parameters_template and u'Parameters' in parameters_template:
            self._get_parameters(parameters_template[u'Parameters'])

    def _get_parameters(self, parameters):
        total_number = 0
        for name in parameters:
            body = parameters[name]
            t = body[u'Type']
            if t == u'ParameterGroup':
                sub_number = self._get_parameters(body[u'Members'])
                profile = {}
                profile[u'Name'] = name
                profile[u'Description'] = body[u'Description']
                profile[u'Type'] = u'Boolean'
                profile[u'SubNumber'] = sub_number
                self.parameters_stack.append(profile)
                total_number += sub_number
            elif t == u'Parameter':
                profile = {}
                profile[u'Name'] = name
                profile[u'Type'] = u'String'
                profile[u'Description'] = body[u'Description']
                if u'MinValue' in body:
                    profile[u'MinValue'] = body[u'MinValue']
                if u'MaxValue' in body:
                    profile[u'MaxValue'] = body[u'MaxValue']
                if u'AllowedValues' in body:
                    profile[u'AllowedValues'] = body[u'AllowedValues']
                self.parameters_stack.append(profile)
                total_number += 1
            else:
                raise Exception(u'unknown type: %s' % t)
        return total_number

    def _load_resources(self):
        resources_string = u''
        with open(u'%s/init.yml' % self.service_dir, u'r') as f:
            start_flag = False
            r = u'Resources'
            o = u'Outputs'
            for line in f:
                if line[0:len(r)] == r:
                    start_flag = True
                elif line[0:len(o)] == o:
                    break
                if start_flag:
                    resources_string = u'%s%s' % (resources_string, line)
        t = Template(resources_string)
        if self.conf_dict and u'Parameters' in self.conf_dict:
            parameters_dict = self.conf_dict[u'Parameters']
        else:
            parameters_dict = {}
        after_render = t.render(parameters_dict)
        resources_template = yaml.safe_load(after_render)
        self.resources_template = resources_template
        if resources_template and u'Resources' in resources_template:
            self._get_instances_configure(resources_template[u'Resources'])

    def _get_instances_configure(self, resources):
        for name in resources:
            body = resources[name]
            t = body[u'Type']
            number = body[u'Number']
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                self._get_instances_configure(body[u'Members'])
            elif t == u'Instance':
                self.instances_stack.append(name)
            else:
                raise Exception(u'unknown type: %s' % t)

    def _launch_resources(self, resources, parent):
        for name in resources:
            body = resources[name]
            t = body[u'Type']
            number = body[u'Number']
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                for i in range(0, number):
                    uuid = u'%s/%s:%d' % (parent, name, i)
                    self._launch_resources(body[u'Members'], uuid)
            elif t == u'Instance':
                total = number
                os_name = body[u'OSName']
                for i in range(0, number):
                    uuid = u'%s/%s:%d' % (parent, name, i)
                    vendor = self.vendor
                    region = self.region
                    profiles_dict = {}
                    for item in self.conf_dict[u'Instances'][name]:
                        real_name = item[len(name)+1:]
                        value = self.conf_dict[u'Instances'][name][item]
                        profiles_dict[real_name] = value
                    specialisms = self.conf_dict[u'Specialisms']
                    if name not in self.instance_dict:
                        self.instance_dict[name] = []
                    self.instance_dict[name].append(Instance(uuid))
                    launch_instance(uuid, profiles_dict, self.stack_name, os_name, vendor, region, specialisms, i)
            else:
                raise Exception(u'unknown type: %s' % t)

    def _init_instances(self, resources, parent):
        for name in  resources:
            body = resources[name]
            t = body[u'Type']
            number = body[u'Number']
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                for i in range(0, number):
                    uuid = u'%s/%s:%d' % (parent, name, i)
                    self._init_instances(body[u'Members'], uuid)
            elif t == u'Instance':
                init_file = u'%s/%s/init.yml' % (self.service_dir, name)
                if not os.path.exists(init_file):
                    continue
                t = self.env.get_template(u'%s/init.yml' % name)
                r = t.render(**self.instance_dict)
                c = yaml.safe_load(r)
                for i in range(0, number):
                    uuid = u'%s/%s:%d' % (parent, name, i)
                    self.current_position = uuid
                    sg_rules = []
                    if u'SecurityGroupRules' in c:
                        for rule in c[u'SecurityGroupRules']:
                            rule = self._explain(rule)
                            if rule:
                                sg_rules.append(rule)
                    init_parameters = []
                    if u'InitParameters' in c:
                        for param in c[u'InitParameters']:
                            param = self._explain(param)
                            if param:
                                init_parameters.append(param)
                    deps = []
                    if u'Depends' in c:
                        for dep in c[u'Depends']:
                            dep = self._explain(dep)
                            if dep:
                                deps.append(dep)
                    set_instance_sg(uuid, sg_rules, self.vendor, self.region)
                    username = get_username(uuid, self.vendor, self.region)
                    hostname = get_public_ip(uuid, self.vendor, self.region)
                    self.before_init.append(uuid)
                    instance_init = InstanceInit(uuid, self.service_dir, name, hostname, username, self.key_filename, \
                                                     deps, init_parameters, self.vendor, self.region, \
                                                     self.lock_before_init, self.lock_on_init, self.lock_after_init, \
                                                     self.before_init, self.on_init, self.after_init, \
                                                     self.send_message, self.set_complete)
                    self.instance_init_list.append(instance_init)
                    instance_init.start()

    def _explain(self, param):
        if type(param) is not types.StringType and type(param) is not types.UnicodeType:
            return param
        flag = u'$$'
        flag_len = len(flag)
        h1 = param.find(flag)
        if h1 == -1:
            return param
        p1 = param[h1+flag_len:]
        h2 = p1.find(flag)
        if h2 == -1:
            raise Exception(u'invalid param: %s' % param)
        p2 = p1[0:h2]
        ret = self._get_attr(p2)
        if ret:
            after_explain = u'%s%s%s' % (param[0:h1], ret, param[h1+flag_len+h2+flag_len:])
            ret1 = self._explain(after_explain)
            return ret1
        else:
            return None

    def _get_attr(self, param):
        # assume the stack name is aa
        # the instance uuid in param maybe:
        # 1 aa/bb:0/cc:0/dd:0
        # 2 aa/bb:0/cc:0/dd:1
        # 3 aa/bb:0/cc:1/dd:0
        # 4 aa/bb:0/cc:1/dd:1
        # 5 aa/bb:1/cc:0/dd:0
        # 6 aa/bb:1/cc:0/dd:1
        # 7 aa/bb:1/cc:1/dd:0
        # 8 aa/bb:1/cc:1/dd:1
        # if the current uuid is aa/xx:1
        # it will accept 1-8
        # if the current uuid is aa/bb:1/cc:0/ee:1
        # it will accept 5-6
        # if the current uuuid is aa/bb:0/mm:0/nn:1
        # it will accept 1-4

        (uuid, attr) = param.split(u'.')
        ori_uuid = uuid
        uuid = uuid.split(u'/')[1:]
        current = self.current_position.split(u'/')[1:]
        len_u = len(uuid) - 1
        len_c = len(current) - 1
        if len_u > len_c:
            len_min = len_c
        else:
            len_min = len_u
        approve = None
        if len_min == 0:
            approve = True
        else:
            root_c = current[0].split(u':')[0]
            root_u = uuid[0].split(u':')[0]
            if root_c != root_u:
                approve = True
            else:
                for i in range(0, len_min):
                    if current[i] != uuid[i]:
                        name_c = current[i].split(u':')[0]
                        name_u = uuid[i].split(u':')[0]
                        if name_c == name_u:
                            approve = False
                        else:
                            approve = True
                        break
                if approve == None:
                    approve = True

        if approve:
            if attr == u'private_ip':
                private_ip = get_private_ip(ori_uuid, self.vendor, self.region)
                return private_ip
            elif attr == u'public_ip':
                public_ip = get_public_ip(ori_uuid, self.vendor, self.region)
                return public_ip
            elif attr == u'hostname':
                hostname = get_hostname(ori_uuid, self.vendor, self.region)
                return hostname
            elif attr == u'uuid':
                return ori_uuid
            else:
                raise Exception(u'unknown attr: %s' % attr)
        else:
            return None

class Erase():
    def __init__(self, stack_name, vendor, region, clin_default_dir):
        driver = vendor_dict[vendor]
        return driver.release_all(stack_name, region)
