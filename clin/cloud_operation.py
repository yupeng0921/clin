#! /usr/bin/env python

from abc import ABCMeta, abstractmethod
class CloudOperation():
    __metaclass__ = ABCMeta
    @abstractmethod
    def __init__(self, stack_name):
        self.__stack_name = stack_name
    @abstractmethod
    def get_region(self, input_region):
        pass
    @abstractmethod
    def get_instance_configure(self, name, param_list):
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
