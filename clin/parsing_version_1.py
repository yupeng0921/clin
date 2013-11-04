#! /usr/bin/env python

import sys
import aws_operation
import yaml

producter_dict = {}
producter_dict[u'aws'] = aws_operation.AwsOperation

def get_parameters(parameter_list, parameter_input_list):
    parameter_dict = {}

class Parameters():
    __parameter_dict = {}
    def __init__(self, parameters, input_parameter_dict, use_default):
        self.__get_parameters(parameters, input_parameter_dict, use_default)

    def __get_parameters(self, parameters, input_parameter_dict, use_default):
        for name in parameters:
            body = parameters[name]
            t = body[u'Type']
            if t == u'ParameterGroup':
                enable = (u'yes', u'Yes', u'YES', u'Y', u'y', True)
                disable = (u'no', u'No', u'NO', u'N', u'n', False)
                if name in input_parameter_dict:
                    inp = input_parameter_dict[name]
                    if not inp in enable+disable:
                        sys.stderr.write('invalid input, %s: %s\n' % (name, inp))
                        sys.exit(1)
                elif use_default:
                    inp = body[u'Default']
                    if not inp in enable+disable:
                        sys.stderr.write('invalid input, %s: %s\n' % (name, inp))
                        sys.exit(1)
                else:
                    prompt = u'%s:' % body[u'Description']
                    while True:
                        inp = raw_input(prompt)
                        if inp in enable:
                            inp = True
                            break
                        elif inp in disable:
                            inp = False
                            break
                self.__parameter_dict[name] = inp
                if inp:
                    self.__get_parameters(body[u'Members'], input_parameter_dict, use_default)
            elif t == u'Parameter':
                if name in input_parameter_dict:
                    inp = input_parameter_dict[name]
                    (ret, reason) = self.__verify_input(body, inp)
                    if ret == False:
                        sys.stderr.write(reason)
                        sys.exit(1)
                elif use_default:
                    inp = body[u'Default']
                    (ret, reason) = self.__verify_input(body, inp)
                    if ret == False:
                        sys.stderr.write(reason)
                        sys.exit(1)
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
                            sys.stdout.write(reason)
                            continue
                        else:
                            break
                self.__parameter_dict[name] = inp

    def __verify_input(self, body, inp):
            if u'MinValue' in body:
                if inp < body[u'MinValue']:
                    reason = 'less than MinValue %s\n' % body[u'MinValue']
                    return (False, reason)
            if u'MaxValue' in body:
                if inp > body[u'MaxValue']:
                    reason = 'larger than MaxValue %s\n' % body[u'MaxValue']
                    return (False, reason)
            if u'AllowedValues' in body:
                if not inp in body[u'AllowedValues']:
                    reason = 'not in AllowedValues %s\n' % body[u'AllowedValues']
                    return (False, reason)
            return (True, None)

    def return_parameter_dict(self):
        return self.__parameter_dict

def deploy_version_1(template, stack_name, producter, parameter_file, \
                         use_default, debug, dump_parameter, conf_dir):
    input_parameter_dict = {}
    input_producter_dict = {}
    if parameter_file:
        p = yaml.safe_load(file(parameter_file))
        if not u'Version' in p:
            sys.stderr.write('parameter file has no version: %s\n', parameter_file)
        elif p[u'Version'] != 1:
            sys.stderr.write('version of parameter file is not 1: %s\n', parameter_file)
        else:
            if u'Parameters' in p:
                for name in p[u'Parameters']:
                    input_parameter_dict[name] = p[u'Parameters'][name]
            if u'Instances' in p:
                for producter in p[u'Instances']:
                    producter_parameter_dict = {}
                    for parameter in p[u'Instances'][producter]:
                        producter_parameter_dict[parameter] = p[u'Instances'][producter][parameter]
                    input_producter_dict[producter] = producter_parameter_dict

    if u'Parameters' in template:
        p = Parameters(template[u'Parameters'], input_parameter_dict, use_default)
        parameter_dict = p.return_parameter_dict()
        print parameter_dict

    valid_producter = producter_dict.keys()
    if producter:
        if not producter in valid_producter:
            sys.stderr(u'invalid producter name: %s\n' % producter)
            sys.stderr(u'only support: %s\n' % valid_producter)
            sys.exit(1)
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
    op_class = producter_dict[producter]
    if producter in input_producter_dict:
        input_param_dict = input_producter_dict[producter]
    else:
        input_param_dict = {}
    op = op_class(stack_name, conf_dir, only_dump, input_param_dict)
    op.get_region()
