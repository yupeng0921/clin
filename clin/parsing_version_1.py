#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import os
import yaml
import time
import types
import threading
from jinja2 import Template, Environment, FileSystemLoader
import paramiko
import scp

productor_dict = {}
import aws_operation
productor_dict[u'aws'] = aws_operation.AwsOperation
import pseudo
productor_dict[u'pseudo'] = pseudo.PseudoOperation

class Instance():
    def __init__(self, uuid):
        attrs = [u'private_ip', u'public_ip', u'uuid']
        for attr in attrs:
            self.__dict__[attr] = u'$$%s.%s$$' % (uuid, attr)

class InstanceProfile(threading.Thread):
    def __init__(self, uuid, folder_dir, instance_name, hostname, username, key_filename, depends, parameters, op, \
                     lock_before_init, lock_on_init, lock_after_init, \
                     before_init, on_init, after_init, lock_op):
        self.uuid = uuid
        self.instance_name = instance_name
        self.folder_dir = folder_dir
        self.hostname = hostname
        self.username = username
        self.key_filename = key_filename
        self.depends = depends
        self.parameters = parameters
        self.op = op
        self.lock_before_init = lock_before_init
        self.lock_on_init = lock_on_init
        self.lock_after_init = lock_after_init
        self.before_init = before_init
        self.on_init = on_init
        self.after_init = after_init
        self.lock_op = lock_op
        self.__running = True
        self.after_scp = False
        threading.Thread.__init__(self, name=uuid)

    def run(self):
        uuid = self.uuid
        instance_name = self.instance_name
        folder_dir = self.folder_dir
        hostname = self.hostname
        username = self.username
        key_filename = self.key_filename
        depends = self.depends
        parameters = self.parameters
        op = self.op
        lock_op = self.lock_op
        lock_before_init = self.lock_before_init
        lock_on_init = self.lock_on_init
        lock_after_init = self.lock_after_init
        before_init = self.before_init
        on_init = self.on_init
        after_init = self.after_init

        lock_op.acquire(True)
        op.open_ssh(uuid)
        lock_op.release()

        print(u'connect ssh start %s' % uuid)
        ssh=paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        retry = 100
        while retry > 0:
            try:
                ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
            except Exception, e:
                time.sleep(3)
            else:
                break
            retry -= 1
        if retry == 0:
            print(u'hostname=%s' % hostname)
            print(u'username=%s' % username)
            print(u'key_filename=%s' % key_filename)
            ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
        print(u'connect ssh stop %s' % uuid)
        print(u'scp start %s' % uuid)
        scopy = scp.SCPClient(ssh.get_transport())
        src = u'%s/%s' % (folder_dir, instance_name)
        dst = u'~/'
        scopy.put(src, dst, True)
        ssh.close()
        print(u'scp stop %s' % uuid)
        self.after_scp = True

        print(u'depends: %s %s' % (depends, uuid))
        if depends:
            while True:
                lock_after_init.acquire(True)
                can_init = True
                for dep in depends:
                    if dep not in after_init:
                        can_init = False
                        break
                lock_after_init.release()
                if can_init:
                    break
                else:
                    if not self.__running:
                        return
                    time.sleep(1)

        lock_before_init.acquire(True)
        lock_on_init.acquire(True)
        before_init.remove(uuid)
        on_init.append(uuid)
        lock_on_init.release()
        lock_before_init.release()

        print(u'do init start %s' % uuid)
        cmd = u'bash ~/%s/init.sh' % instance_name
        if username != u'root':
            cmd = u'sudo %s' % cmd
        for p in parameters:
            cmd = u'%s %s' % (cmd, p)
        ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
        (stdin, stdout, stderr) = ssh.exec_command(cmd, timeout=6000)
        ret = stdout.read()
        ret = stderr.read()
        stdout.close()
        stderr.close()
        ssh.close()
        print(u'do init stop %s' % uuid)

        lock_on_init.acquire(True)
        lock_after_init.acquire(True)
        on_init.remove(uuid)
        after_init.append(uuid)
        lock_after_init.release()
        lock_on_init.release()

        lock_op.acquire(True)
        op.close_ssh(uuid)
        lock_op.release()
        print(u'complete %s' % uuid)

    def stop(self):
        self.__running = False

class DeployVersion1():
    __parameter_dict = {}
    __uuid_dict = {}
    __instance_name_list = []
    __lock_op = threading.Lock()
    def __init__(self, template_dir, stack_name, productor, region, configure_file, \
                     use_default, dump_configure, clin_default_dir):
        input_parameter_dict = {}
        input_productor_dict = {}
        if configure_file:
            with open(configure_file, u'r') as f:
                pf = yaml.safe_load(f)
            if not u'Version' in pf:
                raise Exception(u'parameter file has no version: %s\n' % configure_file)
            elif pf[u'Version'] != 1:
                raise Exception(u'version of parameter file is not 1: %s' % configure_file)
            else:
                if u'Parameters' in pf:
                    for name in pf[u'Parameters']:
                        input_parameter_dict[name] = pf[u'Parameters'][name]
                if u'Resources' in pf:
                    for productor in pf[u'Resources']:
                        productor_parameter_dict = {}
                        for parameter in pf[u'Resources'][productor]:
                            productor_parameter_dict[parameter] = pf[u'Resources'][productor][parameter]
                        input_productor_dict[productor] = productor_parameter_dict

        parameters_string = u''
        with open(u'%s/init.yml' % template_dir, u'r') as f:
            start_flag = False
            p = u'Parameters'
            r = u'Resources'
            o = u'Outputs'
            for line in f:
                if line[0:len(p)] == p:
                    start_flag =True
                if line[0:len(r)] == r:
                    break
                if line[0:len(o)] == o:
                    break
                if start_flag:
                    parameters_string = u'%s%s' % (parameters_string, line)
        pt = yaml.safe_load(parameters_string)
        if pt and u'Parameters' in pt:
            self.__get_parameters(pt[u'Parameters'], input_parameter_dict, use_default, False)

        valid_productor = productor_dict.keys()
        if productor:
            if not productor in valid_productor:
                raise Exception(u'invalid productor name: %s\nonly support: %s' % \
                                    (productor, valid_productor))
        else:
            prompt = u'productor name:'
            while True:
                productor = raw_input(prompt)
                if productor in valid_productor:
                    break

        if dump_configure == u'only':
            only_dump = True
        else:
            only_dump = False

        op = None
        resources_string = u''
        with open(u'%s/init.yml' % template_dir, u'r') as f:
            start_flag = False
            r = u'Resources'
            o = u'Outputs'
            for line in f:
                if line[0:len(r)] == r:
                    start_flag =True
                if line[0:len(o)] == o:
                    break
                if start_flag:
                    resources_string = u'%s%s' % (resources_string, line)
        t = Template(resources_string)
        after_render = t.render(self.__parameter_dict)
        resources_template = yaml.safe_load(after_render)
        if resources_template and u'Resources' in resources_template:
            op_class = productor_dict[productor]
            if productor in input_productor_dict:
                input_param_dict = input_productor_dict[productor]
            else:
                input_param_dict = {}
            op = op_class(stack_name, clin_default_dir, only_dump, input_param_dict)
            op.get_region(region)
            self.__get_group_configure(resources_template[u'Resources'], op)

        if dump_configure in ('yes', 'only'):
            dump_dict = {}
            dump_dict[u'Version'] = 1
            if self.__parameter_dict:
                dump_dict[u'Parameters'] = self.__parameter_dict
            if op:
                productor_instance_dict = {}
                productor_instance_dict[productor] = op.return_all_configure()
                dump_dict[u'Resources'] = productor_instance_dict
            file_name = u'%s-%s.conf' % (stack_name, int(time.time()))
            with open(file_name, 'w') as f:
                yaml.safe_dump(dump_dict, f)

        if only_dump:
            return

        self.__render_dict = {}
        self.__current_position = None
        if op:
            self.__uuid_list = []
            print(u'launching resources')
            self.__launch_group(resources_template[u'Resources'], stack_name, op)
            print(u'waiting resources')
            # for uuid in self.__uuid_list:
            #     op.wait_instance(uuid, 0)
            self.__template_dir = template_dir
            self.__op = op
            self.__render_dict = dict(self.__render_dict, **self.__parameter_dict)
            loader = FileSystemLoader(template_dir)
            self.__template_dir = template_dir
            self.__env = Environment(loader = loader)
            print(u'initing instances')
            self.__before_init = []
            self.__on_init = []
            self.__after_init = []
            self.__lock_before_init = threading.Lock()
            self.__lock_on_init = threading.Lock()
            self.__lock_after_init = threading.Lock()
            self.__instance_profile_list = []
            self.__init_instances(resources_template[u'Resources'], stack_name, op)

            self.__lock_before_init.acquire(True)
            prev_before_init_count = len(self.__before_init)
            self.__lock_before_init.release()
            pending_count = 0

            while True:
                all_after_scp = True
                for instance_profile in self.__instance_profile_list:
                    if not instance_profile.after_scp:
                        all_after_scp = False
                        break
                if all_after_scp:
                    break
                else:
                    time.sleep(1)

            while True:
                self.__lock_before_init.acquire(True)
                before_init_count = len(self.__before_init)
                self.__lock_before_init.release()
                self.__lock_on_init.acquire(True)
                on_init_count = len(self.__on_init)
                self.__lock_on_init.release()
                if before_init_count == 0 and on_init_count == 0:
                    break
                elif on_init_count == 0 and before_init_count == prev_before_init_count:
                    pending_count += 1
                else:
                    pending_count = 0
                prev_before_init_count = before_init_count
                if pending_count >= 10:
                    for instance_profile in self.__instance_profile_list:
                        instance_profile.stop()
                    self.__lock_before_init.acquire(True)
                    before_init = list(self.__before_init)
                    self.__lock_before_init.release()
                    raise Exception(u'seems circle dependency %s' % before_init)
                else:
                    time.sleep(1)

        op.save_to_remote()
        outputs_string = u''
        with open(u'%s/init.yml' % template_dir, u'r') as f:
            start_flag = False
            o = u'Outputs'
            for line in f:
                if line[0:len(o)] == o:
                    start_flag = True
                if start_flag:
                    outputs_string = u'%s%s' % (outputs_string, line)
        t = Template(outputs_string)
        if not self.__render_dict:
            self.__render_dict = dict(self.__render_dict, **self.__parameter_dict)
        after_render = t.render(**self.__render_dict)
        outputs_template = yaml.safe_load(after_render)
        # use a fake current position, ensure do not filter any instance
        self.__current_position = u'%s/&&&&&&&&' % stack_name
        if outputs_template and u'Outputs' in outputs_template:
            output_list = []
            outputs = outputs_template[u'Outputs']
            if outputs:
                for item in outputs:
                    real_item = self.__explain(item)
                    if real_item:
                        output_list.append(real_item)
            print(u'Outputs:')
            for item in output_list:
                print(item)
    def __get_parameters(self, parameters, input_parameter_dict, use_default, disable):
        for name in parameters:
            body = parameters[name]
            t = body[u'Type']
            if t == u'ParameterGroup':
                enable_flag = (u'yes', u'Yes', u'YES', u'Y', u'y', u'True', u'true', True)
                disable_flag = (u'no', u'No', u'NO', u'N', u'n', u'False', u'false', False)
                if disable:
                    inp = False
                elif name in input_parameter_dict:
                    inp = input_parameter_dict[name]
                    if not inp in enable_flag+disable_flag:
                        raise Exception(u'invalid input, %s: %s\n' % (name, inp))
                elif use_default == u'yes':
                    inp = body[u'Default']
                    if not inp in enable_flag+disable_flag:
                        Exception(u'invalid input, %s: %s\n' % (name, inp))
                else:
                    prompt = u'%s:' % body[u'Description']
                    while True:
                        inp = raw_input(prompt)
                        if inp in enable_flag:
                            inp = True
                            break
                        elif inp in disable_flag:
                            inp = False
                            break
                self.__parameter_dict[name] = inp
                if not inp:
                    self.__get_parameters(body[u'Members'], input_parameter_dict, use_default, True)
                else:
                    self.__get_parameters(body[u'Members'], input_parameter_dict, use_default, False)
                
            elif t == u'Parameter':
                if disable:
                    inp = body[u'DisableValue']
                elif name in input_parameter_dict:
                    inp = input_parameter_dict[name]
                    (ret, reason) = self.__verify_input(body, inp)
                    if ret == False:
                        raise Exception(reason)
                elif use_default == u'yes':
                    inp = body[u'Default']
                    (ret, reason) = self.__verify_input(body, inp)
                    if ret == False:
                        raise Exception(reason)
                else:
                    t = type(body[u'Default'])
                    prompt = u'%s:' % body[u'Description']
                    while True:
                        inp = raw_input(prompt)
                        try:
                            inp = t(inp)
                        except ValueError, e:
                            sys.stdout.write(u'wrong input type, should be %s' % t)
                            continue
                        (ret, reason) = self.__verify_input(body, inp)
                        if ret == False:
                            print(reason)
                            continue
                        else:
                            break
                self.__parameter_dict[name] = inp

    def __verify_input(self, body, inp):
        if u'MinValue' in body:
            if inp < body[u'MinValue']:
                reason = 'less than MinValue %s' % body[u'MinValue']
                return (False, reason)
        if u'MaxValue' in body:
            if inp > body[u'MaxValue']:
                reason = 'larger than MaxValue %s' % body[u'MaxValue']
                return (False, reason)
        if u'AllowedValues' in body:
            if not inp in body[u'AllowedValues']:
                reason = 'not in AllowedValues %s' % body[u'AllowedValues']
                return (False, reason)
        return (True, None)

    def __get_group_configure(self, groups, op):
        for name in groups:
            body = groups[name]
            t = body[u'Type']
            number = body[u'Number']
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                self.__get_group_configure(body[u'Members'], op)
            elif t == u'Instance':
                if u'Description' in body:
                    description = body[u'Description']
                else:
                    description = u''
                op.get_instance_configure(name, description)
            else:
                raise Exception(u'Unknown type: %s' % t)

    def __launch_group(self, groups, hierarchy, op):
        for name in groups:
            body = groups[name]
            t = body[u'Type']
            number = body[u'Number']
            if t == u'InstanceGroup':
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__launch_group(body[u'Members'], hierarchy1, op)
            elif t == u'Instance':
                os_name = body[u'OSName']
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__uuid_list.append(hierarchy1)
                    self.__instance_name_list.append(name)
                    if name not in self.__render_dict:
                        self.__render_dict[name] = []
                    self.__render_dict[name].append(Instance(hierarchy1))
                    op.launch_instance(hierarchy1, name, os_name)
            else:
                raise Exception(u'Unknown type: %s' % t)

    def __init_instances(self, groups, hierarchy, op):
        for name in groups:
            body = groups[name]
            t = body[u'Type']
            number = body[u'Number']
            if t == u'InstanceGroup':
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__init_instances(body[u'Members'], hierarchy1, op)
            elif t == u'Instance':
                init_file = u'%s/%s/init.yml' % (self.__template_dir, name)
                if not os.path.exists(init_file):
                    continue
                t = self.__env.get_template(u'%s/init.yml' % name)
                r = t.render(**self.__render_dict)
                c = yaml.safe_load(r)
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__current_position = hierarchy1
                    self.__op = op
                    sg_rules = []
                    if u'SecurityGroupRules' in c:
                        for rule in c[u'SecurityGroupRules']:
                            rule = self.__explain(rule)
                            if rule:
                                sg_rules.append(rule)
                    init_parameters = []
                    if u'InitParameters' in c:
                        for param in c[u'InitParameters']:
                            param = self.__explain(param)
                            if param:
                                init_parameters.append(param)
                    deps = []
                    if u'Depends' in c:
                        for dep in c[u'Depends']:
                            dep = self.__explain(dep)
                            if dep:
                                deps.append(dep)
                    self.__lock_op.acquire(True)
                    op.set_instance_sg(hierarchy1, sg_rules)
                    username, key_filename = op.get_login_user(hierarchy1)
                    hostname = op.get_public_ip(hierarchy1)
                    self.__lock_op.release()
                    self.__before_init.append(hierarchy1)
                    instance_profile = InstanceProfile(hierarchy1, \
                                                           self.__template_dir, name, hostname, username, key_filename, \
                                                           deps, init_parameters, op, \
                                                           self.__lock_before_init, self.__lock_on_init, self.__lock_after_init, \
                                                           self.__before_init, self.__on_init, self.__after_init, \
                                                           self.__lock_op)
                    self.__instance_profile_list.append(instance_profile)
                    instance_profile.start()

    def __explain(self, param):
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
            raise Exception(u'Invalid param: %s' % param)
        p2 = p1[0:h2]
        ret = self.__get_attr(p2)
        if ret:
            after_explain = u'%s%s%s' % (param[0:h1], ret, param[h1+flag_len+h2+flag_len:])
            ret1 = self.__explain(after_explain)
            return ret1
        else:
            return None

    def __get_attr(self, param):
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
        current = self.__current_position.split(u'/')[1:]
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
                self.__lock_op.acquire(True)
                private_ip = self.__op.get_private_ip(ori_uuid)
                self.__lock_op.release()
                return private_ip
            elif attr == u'public_ip':
                self.__lock_op.acquire(True)
                public_ip = self.__op.get_public_ip(ori_uuid)
                self.__lock_op.release()
                return public_ip
            elif attr == u'uuid':
                return ori_uuid
            else:
                raise Exception(u'Unknown attr: %s' % atr)
        else:
            return None

class EraseVersion1():
    def __init__(self, stack_name, productor, region, clin_default_dir):
        valid_productor = productor_dict.keys()
        if productor:
            if not productor in valid_productor:
                raise Exception(u'invalid productor name: %s\nonly support: %s' % \
                                    (productor, valid_productor))
        else:
            prompt = u'productor name:'
            while True:
                productor = raw_input(prompt)
                if productor in valid_productor:
                    break

        op_class = productor_dict[productor]
        op = op_class(stack_name, clin_default_dir, None, None)
        op.get_region(region)
        op.release_all_resources()
