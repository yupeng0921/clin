#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import yaml
import time
import types
import aws_operation
producter_dict = {}
producter_dict[u'aws'] = aws_operation.AwsOperation

class DeployVersion1():
    __parameter_dict = {}
    __uuid_dict = {}
    __instance_name_list = []
    def __init__(self, template, stack_name, producter, region, parameter_file, \
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
            print(u'launching resources')
            self.__launch_group(template[u'Resources'], stack_name, op)
            print(u'waiting resources')
            for uuid in self.__uuid_list:
                op.wait_instance(uuid, 0)
            self.__current_position = None
            self.__config_instances(template[u'Resources'], stack_name, op)

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
                    disable = True
                self.__get_parameters(body[u'Members'], input_parameter_dict, use_default, disable)
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
                            printf(reason)
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
            t = self.__interpret(body[u'Type'])
            number = self.__interpret(body[u'Number'])
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                self.__get_group_configure(body[u'Members'], op)
            elif t == u'Instance':
                description = self.__interpret(body['Description'])
                op.get_instance_configure(name, description)
            else:
                raise Exception(u'Unknown type: %s' % t)

    def __launch_group(self, groups, hierarchy, op):
        for name in groups:
            body = groups[name]
            t = self.__interpret(body[u'Type'])
            number = int(self.__interpret(body[u'Number']))
            if t == u'InstanceGroup':
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__launch_group(body[u'Members'], hierarchy1, op)
            elif t == u'Instance':
                os_name = self.__interpret(body[u'Properties'][u'OSName'])
                sg_rules = []
                for rule in body[u'Properties'][u'SecurityGroupRules']:
                    sg_rules.append(self.__interpret(rule))
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__uuid_list.append(hierarchy1)
                    self.__instance_name_list.append(name)
                    op.launch_instance(hierarchy1, name, os_name, sg_rules)
            else:
                raise Exception(u'Unknown type: %s' % t)

    def __config_instances(self, groups, hierarchy, op):
        for name in groups:
            body = groups[name]
            t = self.__interpret(body[u'Type'])
            number = int(self.__interpret(body[u'Number']))
            if t == u'InstanceGroup':
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__config_instances(body[u'Members'], hierarchy1, op)
            elif t == u'Instance':
                for i in range(0, number):
                    hierarchy1 = u'%s/%s:%d' % (hierarchy, name, i)
                    self.__current_position = hierarchy1
                    sg_rules = []
                    properties = body[u'Properties']
                    if u'SecurityGroupRules' in properties:
                        for rule in properties[u'SecurityGroupRules']:
                            sg_rules.append(self.__interpret(rule))
                    if u'InitScript' in properties:
                        init_script = self.__interpret(body[u'Properties'][u'InitScript'])
                    init_parameters = []
                    if u'InitParameters' in properties:
                        for p in body[u'Properties'][u'InitParameters']:
                            init_parameters.append(self.__interpret(p))
                    print(sg_rules)
                    print(init_script)
                    print(init_parameters)

    def __interpret(self, expr):
        t = type(expr)
        if (t is types.UnicodeType) or (t is types.StringType):
            if expr[0:2] == u'$$' and expr[-2:] == u'$$':
                expr = expr[2:-2]
                return self.__run_buildin_func(expr)
            else:
                return expr
        else:
            return expr

    def __run_buildin_func(self, expr):
        l = expr.split(u'.')
        if l[0] == 'Parameter':
            return self.__parameter_dict[l[1]]
        elif l[0] in self.__instance_name_list:
            return self.__get_instance_attr(l)
        else:
            raise Exception(u'Unknown expr: %s' % expr)

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
        ret = u''
        for uuid in valid_uuid_list:
            ret = u'%s %s %s ' % (ret, uuid, attr)
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
