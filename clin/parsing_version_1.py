#! /usr/bin/env python

import sys
import aws_operation

producter_dict = {}
producter_dict[u'aws'] = aws_operation.AwsOperation

def get_parameters(parameter_list, parameter_input_list):
    parameter_dict = {}

class Parameters():
    __parameter_dict = {}
    def __init__(self, parameters, parameter_input_list):
        self.get_parameters(parameters, parameter_input_list)
    def get_parameters(self, parameters, parameter_input_list):
        for name in parameters:
            body = parameters[name]
            t = body[u'Type']
            if t == u'ParameterGroup':
                prompt = u'%s:' % name
                while True:
                    inp = raw_input(prompt)
                    if inp in (u'yes', u'Yes', u'YES', u'Y', u'y'):
                        inp = True
                        break
                    elif inp in (u'no', u'No', u'NO', u'N', u'n'):
                        inp = False
                        break
                self.__parameter_dict[name] = inp
                if inp:
                    self.get_parameters(body[u'Members'], parameter_input_list)
            elif t == u'Parameter':
                prompt = u'%s:' % name
                inp = raw_input(prompt)
                self.__parameter_dict[name] = inp
    def return_parameter_dict(self):
        return self.__parameter_dict

def deploy_version_1(template, stack_name, producter, region, parameter_file, \
                         use_default, debug, dump_parameter, parameter_input_list, instance_conf_input_list):

    if u'Parameters' in template:
        p = Parameters(template[u'Parameters'], parameter_input_list)
        parameter_dict = p.return_parameter_dict()
        print parameter_dict

    sys.exit(0)
    valid_producter = producter_dict.keys()
    if producter:
        if not producter in valid_producter:
            sys.stderr(u'invalid producter name: %s\n' % producter)
            sys.stderr(u'only support: %s\n' % unicode(valid_producter))
            sys.exit(1)
    else:
        prompt = u'producter name:'
        while True:
            producter = raw_input(prompt)
            if producter in valid_producter:
                break

    op_class = producter_dict[producter]
    op = op_class(stack_name)
    op.get_region(regoin)
