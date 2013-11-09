#! /usr/bin/env python

# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod
class CloudOperation():
    __metaclass__ = ABCMeta
    @abstractmethod
    def __init__(self, stack_name, conf_dir, only_dump, input_param_dict):
        pass
    @abstractmethod
    def get_region(self, input_region):
        pass
    @abstractmethod
    def get_instance_configure(self, name, description):
        pass
    @abstractmethod
    def launch_instance(self, uuid, name, os_name, security_group_rules):
        pass
    @abstractmethod
    def set_instance_sg(self, uuid, sg_rules):
        pass
    @abstractmethod
    def wait_instance(self, uuid, timeout):
        pass
    @abstractmethod
    def get_login_user(self, uuid):
        pass
    @abstractmethod
    def get_public_ip(self, uuid):
        pass
    @abstractmethod
    def get_private_ip(self, uuid):
        pass
    @abstractmethod
    def open_ssh(self, uuid):
        pass
    @abstractmethod
    def close_ssh(self, uuid):
        pass
    @abstractmethod
    def terminate_instance(self, uuid):
        pass
    @abstractmethod
    def release_all_resources(self):
        pass
    @abstractmethod
    def return_all_configure(self):
        pass
