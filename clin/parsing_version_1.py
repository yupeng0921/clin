#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import yaml
import time
import types
from jinja2 import Template, Environment, FileSystemLoader

producter_dict = {}
import aws_operation
producter_dict[u'aws'] = aws_operation.AwsOperation
import pseudo
producter_dict[u'pseudo'] = pseudo.PseudoOperation

class Instance():
    def __init__(self, uuid):
        attrs = [u'private_ip', u'public_ip']
        for attr in attrs:
            self.__dict__[attr] = u'$$%s.%s$$' % (uuid, attr)

class DeployVersion1():
    __parameter_dict = {}
    __uuid_dict = {}
    __instance_name_list = []
    def __init__(self, template, template_dir, stack_name, producter, region, parameter_file, \
                     use_default, debug, dump_parameter, conf_dir):
        input_parameter_dict = {}
        input_producter_dict = {}
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
                    for producter in pf[u'Resources']:
                        producter_parameter_dict = {}
                        for parameter in pf[u'Resources'][producter]:
                            producter_parameter_dict[parameter] = pf[u'Resources'][producter][parameter]
                        input_producter_dict[producter] = producter_parameter_dict

        if u'Parameters' in template:
            self.__get_parameters(template[u'Parameters'], input_parameter_dict, use_default, False)

        valid_producter = producter_dict.keys()
        if producter:
            if not producter in valid_producter:
                raise Exception(u'invalid producter name: %s\nonly support: %s' % \
                                    (producter, valid_producter))
        else:
            prompt = u'producter name:'
            while True:
                producter = raw_input(prompt)
                if producter in valid_producter:
                    break

        if dump_parameter == u'only':
            only_dump = True
        else:
            only_dump = False

        op = None
        if u'Resources' in template:
            op_class = producter_dict[producter]
            if producter in input_producter_dict:
                input_param_dict = input_producter_dict[producter]
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
                producter_instance_dict = {}
                producter_instance_dict[producter] = op.return_all_configure()
                dump_dict[u'Resources'] = producter_instance_dict
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
            self.__env = Environment(loader = loader)
            self.__init_instances(template[u'Resources'], stack_name, op)

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
                t = self.__env.get_template(u'%s/init.yml' % name)
                r = t.render(**self.__render_dict)
                c = yaml.safe_load(r)
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)

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

    def __get_instance_attr(self, l):
        name = l[0]
        attr = l[1]
        head = self.__current_position.find(u'/')
        position = self.__current_position[head:]
        valid_uuid_list = []
        if name in position:
            h1 = position.find(name)
            h2 = position[h1:].find(u'/')
            prefix = position[0:h1+h2]
            for uuid in self.__uuid_list:
                if prefix == uuid[head:][0:h1+h2]:
                    valid_uuid_list.append(uuid)
        else:
            for uuid in self.__uuid_list:
                if name in uuid[head:]:
                    valid_uuid_list.append(uuid)

        if attr == u'private_ip':
            func = self.__op.get_private_ip
        elif attr == u'public_ip':
            func = self.__op.get_public_ip
        else:
            raise Exception(u'Unknown attr: %s' % attr)

        ret = u''
        for uuid in valid_uuid_list:
            val = func(uuid)
            ret = u'%s %s %s ' % (ret, uuid, val)
        ret = ret.strip()
        return ret

class EraseVersion1():
    def __init__(self, stack_name, producter, region, conf_dir):
        valid_producter = producter_dict.keys()
        if producter:
            if not producter in valid_producter:
                raise Exception(u'invalid producter name: %s\nonly support: %s' % \
                                    (producter, valid_producter))
        else:
            prompt = u'producter name:'
            while True:
                producter = raw_input(prompt)
                if producter in valid_producter:
                    break

        op_class = producter_dict[producter]
        op = op_class(stack_name, conf_dir, None, None)
        op.get_region(region)
        op.release_all_resources()
