#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import getopt
import yaml
from parsing_version_1 import deploy_version_1

def load_local_template_file(template_file):
    with open(template_file) as f:
        template = yaml.safe_load(f)
    return template

def load_remote_template_file(service_name):
    return {}

def load_template(service_name):
    local_flag = u'file://'
    length = len(local_flag)
    if service_name[0:length] == local_flag:
        return load_local_template_file(service_name[length:])
    else:
        return load_remote_template_file(service_name)
sub_commands = {}
def subcmd(name):
    def _subcmd(func):
        sub_commands[name] =func
        def __subcmd(*args, **kwargs):
            ret = func(*args, **kwargs)
            return ret
        return __subcmd
    return _subcmd

@subcmd(u'deploy')
def clin_deploy(argv):

    def deploy_usage():
        print(u'deploy_usage')

    long_params = [u'stack-name=', u'producter=', u'region=', \
                       u'parameter=', u'instance-conf=', \
                       u'parameter-file=', u'dump-parameter=', \
                       u'yes', u'debug']
    try:
        opts, args = getopt.gnu_getopt(argv, u'y', long_params)
    except getopt.GetoptError, e:
        deploy_usage()
        sys.exit(1)

    stack_name = None
    producter = None
    region = None
    parameter_file = None
    use_default = False
    debug = False
    dump_parameter = u'no'
    parameter_list = []
    instance_conf_list = []
    for o, a in opts:
        if o == u'--stack-name':
            stack_name = a
        elif o == u'--producter':
            producter = a
        elif o == u'--region':
            producter = a
        elif o == u'--parameter-file':
            parameter_file = a
        elif o == u'-template-file':
            template_file = a
        elif o == u'--parameter':
            parameter_list.append(a)
        elif o == u'--instance-conf':
            instance_conf_list.append(a)
        elif o == u'--dump-parameter':
            if a in (u'no', u'yes', u'only'):
                dump_parameter = a
            else:
                print(u'invalid dump-parameter: %s, should be no, yes, only' % a)
                sys.exit(1)
        elif o in (u'-y', '--yes'):
            use_default = True
        elif o == u'--debug':
            debug = True
        else:
            print(u'invalid args: %s %s' % (o, a))
            sys.exit(1)

    if len(args) != 1:
        print(u'should specific 1 and only 1 service name')
        for a in args:
            print(a)
        deploy_usage()
        sys.exit(1)
    service_name = args[0]

    if not stack_name:
        print(u'no stack name')
        deploy_usage()
        sys.exit(1)

    template = load_template(service_name)

    if u'Version' in template:
        v = template[u'Version']
        if v == 1:
            deploy_version_1(template, stack_name, producter, region, parameter_file, \
                                 use_default, debug, dump_parameter, parameter_list, instance_conf_list)
        else:
            print(u'unsupport version: %s' % unicode(v))
            sys.exit(1)
    else:
        print(u'should specific Version in template')
        sys.exit(1)

@subcmd(u'describe')
def clin_describe(argv):
    print(argv)

@subcmd(u'erase')
def clin_erase(argv):
    print(argv)

@subcmd(u'update')
def clin_update(argv):
    print(argv)

def usage():
    print(u'usage')

def main():
    try:
        if sys.argv[1] == u'--help':
            usage()
            sys.exit(0)
        elif sys.argv[1] == u'--version':
            print(u'version')
            sys.exit(0)
        else:
            sub_command = sub_commands[sys.argv[1]]
    except KeyError, e:
        usage()
        sys.exit(1)
    except IndexError, e:
        usage()
        sys.exit(1)

    sub_command(sys.argv[2:])

if __name__ == u'__main__':
    main()
