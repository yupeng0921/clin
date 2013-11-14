#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import os
import yaml
import time
import types
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

class RunInit():
    def __init__(self, uuid, name, hostname, username, key_filename, depends, parameters):
        self.uuid = uuid
        self.name = name
        self.hostname = hostname
        self.username = username
        self.key_filename = key_filename
        self.depends = depends
        self.parameters = parameters

class DeployVersion1():
    __parameter_dict = {}
    __uuid_dict = {}
    __instance_name_list = []
    def __init__(self, template, template_dir, stack_name, productor, region, parameter_file, \
                     use_default, debug, dump_parameter, conf_dir):
        input_parameter_dict = {}
        input_productor_dict = {}
        if parameter_file:
            with open(parameter_file, u'r') as f:
                pf = yaml.safe_load(f)
            if not u'Version' in pf:
                raise Exception(u'parameter file has no version: %s\n' % parameter_file)
            elif pf[u'Version'] != 1:
                raise Exception(u'version of parameter file is not 1: %s' % parameter_file)
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

        if u'Parameters' in template:
            self.__get_parameters(template[u'Parameters'], input_parameter_dict, use_default, False)

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

        if dump_parameter == u'only':
            only_dump = True
        else:
            only_dump = False

        op = None
        if u'Resources' in template:
            op_class = productor_dict[productor]
            if productor in input_productor_dict:
                input_param_dict = input_productor_dict[productor]
            else:
                input_param_dict = {}
            op = op_class(stack_name, conf_dir, only_dump, input_param_dict)
            op.get_region(region)
            self.__get_group_configure(template[u'Resources'], op)

        if dump_parameter in ('yes', 'only'):
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

        if op:
            self.__uuid_list = []
            self.__render_dict = {}
            print(u'launching resources')
            self.__launch_group(template[u'Resources'], stack_name, op)
            print(u'waiting resources')
            for uuid in self.__uuid_list:
                op.wait_instance(uuid, 0)
            self.__current_position = None
            self.__template_dir = template_dir
            self.__op = op
            self.__render_dict = dict(self.__render_dict, **self.__parameter_dict)
            loader = FileSystemLoader(template_dir)
            self.__template_dir = template_dir
            self.__env = Environment(loader = loader)
            print(u'initing instances')
            self.__not_init = []
            self.__already_init = []
            self.__init_instances(template[u'Resources'], stack_name, op)
            while len(self.__not_init) > 0:
                tmp_list = []
                for run_init in self.__not_init:
                    can_run = True
                    if run_init.depends:
                        for dep in run_init.depends:
                            if dep not in self.__already_init:
                                can_run = False
                                break
                    if can_run:
                        ssh=paramiko.SSHClient()
                        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        hostname = run_init.hostname
                        username = run_init.username
                        key_filename = run_init.key_filename
                        cmd = u'bash ~/%s/init.sh' % run_init.name
                        if username != u'root':
                            cmd = u'sudo %s' % cmd
                        for p in run_init.parameters:
                            cmd = u'%s %s' % (cmd, p)
                        print(hostname)
                        print(username)
                        print(key_filename)
                        print(cmd)
                        ssh.connect(hostname=hostname, username=username, key_filename=key_filename)
                        (stdin, stdout, stderr) = ssh.exec_command(cmd, timeout=6000)
                        print("stdout:")
                        print(stdout.read())
                        print("stderr:")
                        print(stderr.read())
                        stdout.close()
                        stderr.close()
                        ssh.close()
                        self.__already_init.append(run_init.uuid)
                        tmp_list.append(run_init)
                if not tmp_list:
                    raise Exception('can not init any more')
                for run_init in tmp_list:
                    self.__not_init.remove(run_init)

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
                elif use_default:
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
                elif use_default:
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
            number = self.__get_number(body[u'Number'])
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                self.__get_group_configure(body[u'Members'], op)
            elif t == u'Instance':
                description = body['Description']
                op.get_instance_configure(name, description)
            else:
                raise Exception(u'Unknown type: %s' % t)

    def __launch_group(self, groups, hierarchy, op):
        for name in groups:
            body = groups[name]
            t = body[u'Type']
            number = self.__get_number(body[u'Number'])
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
            number = self.__get_number(body[u'Number'])
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
                    sg_rules.append(u'tcp 22 0.0.0.0/0')
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
                    op.set_instance_sg(hierarchy1, sg_rules)
                    username, key_filename = op.get_login_user(hierarchy1)
                    hostname = op.get_public_ip(hierarchy1)
                    op.open_ssh(hierarchy1)
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
                    scopy = scp.SCPClient(ssh.get_transport())
                    src = u'%s/%s' % (self.__template_dir, name)
                    dst = u'~/'
                    scopy.put(src, dst, True)
                    ssh.close()
                    op.close_ssh(hierarchy1)
                    run_init = RunInit(hierarchy1, name, hostname, username, key_filename, deps, init_parameters)
                    self.__not_init.append(run_init)

    def __get_number(self, number):
        t = type(number)
        if t is not types.IntType:
            if t is types.StringType or t is types.UnicodeType:
                if number in self.__parameter_dict:
                    number = self.__parameter_dict[number]
                    if type(number) is not types.IntType:
                        raise Exception(u'Unsupport number type: %s %s' % (number, type(number)))
                else:
                    raise Exception(u'Unknown number: %s' % number)
            else:
                raise Exception(u'Unsupport number type: %s %s' % (number, t))
        return number

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
                return self.__op.get_private_ip(ori_uuid)
            elif attr == u'public_ip':
                return self.__op.get_public_ip(ori_uuid)
            elif attr == u'uuid':
                return ori_uuid
            else:
                raise Exception(u'Unknown attr: %s' % atr)
        else:
            return None

class EraseVersion1():
    def __init__(self, stack_name, productor, region, conf_dir):
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
        op = op_class(stack_name, conf_dir, None, None)
        op.get_region(region)
        op.release_all_resources()
