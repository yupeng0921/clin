#! /usr/bin/env python

import sys
import yaml
import time
import types
import aws_operation
producter_dict = {}
producter_dict[u'aws'] = aws_operation.AwsOperation

class Parameters():
    __parameter_dict = {}
    def __init__(self, parameters, input_parameter_dict, use_default):
        self.__get_parameters(parameters, input_parameter_dict, use_default)

    def __get_parameters(self, parameters, input_parameter_dict, use_default, disable=False):
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
                        sys.stderr.write(u'invalid input, %s: %s\n' % (name, inp))
                        sys.exit(1)
                elif use_default:
                    inp = body[u'Default']
                    if not inp in enable_flag+disable_flag:
                        sys.stderr.write(u'invalid input, %s: %s\n' % (name, inp))
                        sys.exit(1)
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

buildin_func = {}
def buildin(name):
    def _buildin(func):
        buildin_func[name] = func
        def __buildin(*args, **kwargs):
            ret = func(*args, **kwargs)
            return ret
        return __buildin
    return _buildin

global_param_dict = {}
@buildin(u'Parameter')
def get_parameter(name):
    return global_param_dict[name]

def interpret(expr):
    t = type(expr)
    if t is types.IntType:
        return expr
    elif (t is types.UnicodeType) or (t is types.StringType):
        if expr[0:2] == u'$$' and expr[-2:] == u'$$':
            expr = expr[2:-2]
            l = expr.split(u'.')
            if len(l) != 2:
                sys.stderr.write(u'invalid expr, %s' % expr)
            [func_name, param] = l
            return buildin_func[func_name](param)
        else:
            return expr
    else:
        return expr

def get_group_configure(groups, op):
    for name in groups:
        body = groups[name]
        t = interpret(body[u'Type'])
        number = interpret(body[u'Number'])
        if number <= 0:
            continue
        if t == u'InstanceGroup':
            get_group_configure(body[u'Members'], op)
        elif t == u'Instance':
            description = interpret(body['Description'])
            op.get_instance_configure(name, description)
        else:
            sys.stderr.write(u'Unknown type: %s\n' % t)

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

    param = None
    if u'Parameters' in template:
        param = Parameters(template[u'Parameters'], input_parameter_dict, use_default)
        global global_param_dict
        global_param_dict = param.return_parameter_dict()

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

    op = None
    if u'Resources' in template:
        op_class = producter_dict[producter]
        if producter in input_producter_dict:
            input_param_dict = input_producter_dict[producter]
        else:
            input_param_dict = {}
        op = op_class(stack_name, conf_dir, only_dump, input_param_dict)
        op.get_region()
        get_group_configure(template[u'Resources'], op)

    if dump_parameter in ('yes', 'only'):
        dump_dict = {}
        dump_dict[u'Version'] = 1
        if param:
            dump_dict[u'Parameters'] = param.return_parameter_dict()
        if op:
            producter_instance_dict = {}
            producter_instance_dict[producter] = op.return_all_configure()
            dump_dict[u'Instancnes'] = producter_instance_dict
        # dump_data = yaml.safe_dump(dump_dict)
        file_name = u'%s-%s.conf' % (stack_name, int(time.time()))
        with open(file_name, 'w') as f:
            yaml.safe_dump(dump_dict, f)

    if only_dump:
        sys.exit(0)
