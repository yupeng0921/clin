#! /usr/bin/env python

# -*- coding: utf-8 -*-

class PseudoOperation():
    def __init__(self, stack_name, conf_dir, only_dump, input_param_dict):
        self.__stack_name = stack_name

    def get_region(self, input_region):
        pass

    def get_instance_configure(self, name, description):
        pass

    def launch_instance(self, uuid, name, os_name):
        print(u'launch instance:')
        print(uuid)
        print(name)
        print(os_name)
        print(u'')

    def set_instance_sg(self, uuid, sg_rules):
        pass

    def wait_instance(self, uuid, timeout):
        print(u'wait instance:')
        print(uuid)
        print(timeout)

    def get_login_user(self, uuid):
        return (u'root', u'~/.clin/pseudo/pseudo.pem')

    def get_public_ip(self, uuid):
        return u'%s:pub' % uuid

    def get_private_ip(self, uuid):
        return u'%s:pri' % uuid

    def open_ssh(self, uuid):
        pass

    def close_ssh(self, uuid):
        pass

    def terminate_instance(self, uuid):
        pass

    def release_all_resources(self):
        pass

    def return_all_configure(self):
        return {}
