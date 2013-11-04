#! /usr/bin/env python

from abc import ABCMeta, abstractmethod
class CloudOperation():
    __metaclass__ = ABCMeta
    @abstractmethod
    def __init__(self, stack_name, conf_dir, only_dump, input_param_dict):
        pass
    @abstractmethod
    def get_region(self):
        pass
    @abstractmethod
    def get_instance_configure(self, name, description):
        pass
    @abstractmethod
    def launch_instance(self, uuid, name, os_name, security_group_rules):
        pass
    @abstractmethod
    def wait_instance(self, uuid):
        pass
    @abstractmethod
    def get_public_ip(self, uuid):
        pass
    @abstractmethod
    def get_private_ip(self, uuid):
        pass
    @abstractmethod
    def terminate_instance(self, uuid):
        pass
    @abstractmethod
    def terminate_all_instances(self):
        pass
    @abstractmethod
    def return_all_configure(self):
        pass
