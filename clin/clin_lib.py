#! /usr/bin/env python

import os
import types
import yaml
from jinja2 import Template, Environment, FileSystemLoader
from profile_ops import generate_profile, verify_profile

vendor_dict = {}
import aws_driver
vendor_dict[u'aws'] = aws_driver.driver

def get_vendors():
    return [u'aws']

def get_regions(vendor):
    driver = vendor_dict[vendor]
    return driver.get_regions()

def get_specialisms(vendor, region):
    driver = vendor_dict[vendor]
    return driver.get_specialisms(region)

def verify_specialisms(profiles, vendor, region):
    driver = vendor_dict[vendor]
    return driver.verify_specialisms(profiles, region)

def get_instance_profiles(vendor, region, specialisms):
    driver = vendor_dict[vendor]
    return driver.get_instance_profiles(region, specialisms)

def verify_instance_profiles(profiles, vendor, region, specialisms):
    driver = vendor_dict[vendor]
    return driver.verify_instance_profiles(profiles, region, specialisms)

def create_keypair(keypair_name, vendor, region):
    driver = vendor_dict[vendor]
    return driver.create_keypair(keypair_name, region)

def launch_instance(uuid, profiles, keypair_name, vendor, region, specialisms):
    driver = vendor_dict[vendor]
    return driver.launch_instance(uuid, profiles, keypair_name, region, specialisms)

class Deploy():
    def __init__(self, service_dir, stack_name, vendor, region, \
                     configure_file, use_compile, \
                     clin_default_dir):
        self.service_dir = service_dir
        self.stack_name = stack_name
        self.vendor = vendor
        self.region = region
        if configure_file:
            with open(configure_file, u'r') as f:
                self.configure_dict = yaml.safe_load(f)
        else:
            self.configure_dict = {}
        self.use_compile = use_compile
        self.clin_default_dir = clin_default_dir
        self.stage = u'init'
        self.conf_dict = {}
        self.conf_dict[u'Parameters'] = {}
        self.conf_dict[u'Specialisms'] = {}
        self.conf_dict[u'Instances'] = {}
        self.parameters_stack = []
        self.instances_stack = []
        self.resources_template = None
        self._load_parameters()
    def get_next(self):
        while True:
            if self.stage == u'init':
                self.stage = u'vendor'
                continue
            elif self.stage == u'vendor':
                allowed_values = get_vendors()
                profile = generate_profile(u'Vendor', u'String', u'Vendor', allowed_values)
                if self.vendor:
                    profile[u'Value'] = self.vendor
                    ret = verify_profile(profile)
                    if ret:
                        raise Exception(ret)
                    self.stage = u'Region'
                    continue
                else:
                    self.stage = u'getting_vendor'
                    return [profile]
            elif self.stage == u'Region':
                vendor = self.vendor
                allowed_values = get_regions(vendor)
                profile = generate_profile(u'Region', u'String', u'Region', allowed_values)
                if self.region:
                    profile[u'Value'] = self.region
                    ret = verify_profile(profile)
                    if ret:
                        raise Exception(ret)
                    self.stage = u'parameters'
                    continue
                else:
                    self.stage = u'getting_region'
                    return [profile]
            elif self.stage == u'parameters':
                if self.parameters_stack:
                    profile = self.parameters_stack.pop()
                    name = profile[u'Name']
                    if self.configure_dict and \
                            u'Parameters' in self.configure_dict and \
                            name in self.configure_dict[u'Parameters']:
                        profile[u'Value'] = self.configure_dict[u'Parameters'][name]
                        ret = verify_profile(profile)
                        if ret:
                            raise Exception(ret)
                        if profile[u'Type'] == u'ParameterGroup' and not profile[u'Value']:
                            for i in range(0, profile[u'SubNumber']):
                                self.parameters_stack.pop()
                        self.conf_dict[u'Parameters'][name] = profile[u'Value']
                        continue
                    else:
                        self.stage = u'getting_parameter'
                        return [profile]
                else:
                    self._load_resources()
                    self.stage = u'specialisms'
                    continue
            elif self.stage == u'specialisms':
                 vendor = self.vendor
                 region = self.region
                 profiles = get_specialisms(vendor, region)
                 if profiles:
                     if u'Specialisms' in self.configure_dict and \
                             self.configure_dict[u'Specialisms']:
                         for profile in profiles:
                             name = profile['Name']
                             if name in self.configure_dict[u'Specialisms']:
                                 profile[u'Value'] = self.configure_dict[u'Specialisms'][name]
                             else:
                                 raise Exception(u'no %s in configure file' % name)
                         ret = verify_specialisms(profiles, vendor, region)
                         if ret:
                             raise Exception(ret)
                         else:
                             for profile in profiles:
                                 name = profile[u'Name']
                                 value = profile[u'Value']
                                 self.conf_dict[u'Specialisms'][name] = value
                             self.stage = u'instances'
                             continue
                     else:
                         self.stage = u'getting_specialisms'
                         return profiles
                 else:
                     self.stage = u'instances'
                     continue
            elif self.stage == u'instances':
                if self.instances_stack:
                    instance_name = self.instances_stack.pop()
                    vendor = self.vendor
                    region = self.region
                    specialisms = self.conf_dict[u'Specialisms']
                    profiles = get_instance_profiles(vendor, region, specialisms)
                    for profile in profiles:
                        profile[u'Name'] = u'%s %s' % (instance_name, profile[u'Name'])
                    if self.configure_dict and \
                            u'Instances' in self.configure_dict and \
                            instance_name in self.configure_dict[u'Instances']:
                        for profile in profiles:
                            name = profile[u'Name']
                            if name in self.configure_dict[u'Instances'][instance_name]:
                                profile[u'Value'] = self.configure_dict[u'Instances'][instance_name][name]
                            else:
                                raise Exception(u'no %s in configure file' % name)
                        ret = verify_instance_profiles(profiles, vendor, region, specialisms)
                        if ret:
                            raise Exception(ret)
                        else:
                            self.conf_dict[u'Instances'][instance_name] = {}
                            for profile in profiles:
                                name = profile[u'Name']
                                value = profile[u'Value']
                                self.conf_dict[u'Instances'][instance_name][name] = value
                            stage = u'instances'
                    else:
                        self.instance_name = instance_name
                        self.stage = u'getting_instances'
                        return profiles
                else:
                    self.stage = u'getting_end'
                    return None
            else:
                raise Exception(self.stage)

    def set_profiles(self, profiles):
        if self.stage == u'getting_vendor':
            profile = profiles[0]
            ret = verify_profile(profile)
            if ret:
                return ret
            self.vendor = profile[u'Value']
            self.stage = u'Region'
            return None
        elif self.stage == u'getting_region':
            vendor = self.vendor
            profile = profiles[0]
            ret = verify_profile(profile)
            if ret:
                return ret
            self.region = profile[u'Value']
            self.stage = u'parameters'
            return None
        elif self.stage == u'getting_parameter':
            profile = profiles[0]
            ret = verify_profile(profile)
            if ret:
                return ret
            if profile[u'Type'] == u'ParameterGroup' and not profile[u'Value']:
                for i in ragne(0, profile[u'SubNumber']):
                    self.parameters_stack.pop()
            name = profile[u'Name']
            self.conf_dict[u'Parameters'][name] = profile[u'Value']
            self.stage = u'parameters'
            return None
        elif self.stage == u'getting_specialisms':
            vendor = self.vendor
            region = self.region
            ret = verify_specialisms(profiles, vendor, region)
            if ret:
                return ret
            else:
                for profile in profiles:
                    name = profile[u'Name']
                    value = profile[u'Value']
                    self.conf_dict[u'Specialisms'][name] = value
                self.stage = u'instances'
                return None
        elif self.stage == u'getting_instances':
            vendor = self.vendor
            region = self.region
            specialisms = self.conf_dict[u'Specialisms']
            ret = verify_instance_profiles(profiles, vendor, region, specialisms)
            if ret:
                return ret
            else:
                profile = profiles[0]
                name = profile[u'Name']
                pos =name.index(' ')
                instance_name = name[0:pos]
                self.conf_dict[u'Instances'][instance_name] = {}
                for profile in profiles:
                    name = profile[u'Name']
                    value = profile[u'Value']
                    self.conf_dict[u'Instances'][self.instance_name][name] = value
                self.stage = u'instances'
                return None
        else:
            raise Exception(u'invalid stage: %s' % self.stage)

    def get_configure(self):
        return self.conf_dict

    def launch_resources(self):
        if not self.resources_template:
            raise Exception(u'not load resources template')
        if self.resources_template and u'Resources' in self.resources_template:
            vendor = self.vendor
            region = self.region
            keypair_path = create_keypair(self.stack_name, vendor, region)
            self.keypair_path = keypair_path
            self._launch_resources(self.resources_template[u'Resources'], self.stack_name)

    def _load_parameters(self):
        parameters_string = u''
        with open(u'%s/init.yml' % self.service_dir, u'r') as f:
            start_flag = False
            p = u'Parameters'
            r = u'Resources'
            o = u'Outputs'
            for line in f:
                if line[0:len(p)] == p:
                    start_flag = True
                elif line[0:len(r)] == r:
                    break
                elif line[0:len(o)] == o:
                    break
                if start_flag:
                    parameters_string = u'%s%s' % (parameters_string, line)
        parameters_template = yaml.safe_load(parameters_string)
        if parameters_template and u'Parameters' in parameters_template:
            self._get_parameters(parameters_template[u'Parameters'])

    def _get_parameters(self, parameters):
        total_number = 0
        for name in parameters:
            body = parameters[name]
            t = body[u'Type']
            if t == u'ParameterGroup':
                sub_number = self._get_parameters(body[u'Members'])
                profile = {}
                profile[u'Name'] = name
                profile[u'Description'] = body[u'Description']
                profile[u'Type'] = u'Boolean'
                profile[u'SubNumber'] = sub_number
                self.parameters_stack.append(profile)
                total_number += sub_number
            elif t == u'Parameter':
                profile = {}
                profile[u'Name'] = name
                profile[u'Type'] = u'String'
                profile[u'Description'] = body[u'Description']
                if u'MinValue' in body:
                    profile[u'MinValue'] = body[u'MinValue']
                if u'MaxValue' in body:
                    profile[u'MaxValue'] = body[u'MaxValue']
                if u'AllowedValues' in body:
                    profile[u'AllowedValues'] = body[u'AllowedValues']
                self.parameters_stack.append(profile)
                total_number += 1
            else:
                raise Exception(u'unknown type: %s' % t)
        return total_number

    def _load_resources(self):
        resources_string = u''
        with open(u'%s/init.yml' % self.service_dir, u'r') as f:
            start_flag = False
            r = u'Resources'
            o = u'Outputs'
            for line in f:
                if line[0:len(r)] == r:
                    start_flag = True
                elif line[0:len(o)] == o:
                    break
                if start_flag:
                    resources_string = u'%s%s' % (resources_string, line)
        t = Template(resources_string)
        if self.conf_dict and u'Parameters' in self.conf_dict:
            parameters_dict = self.conf_dict[u'Parameters']
        else:
            parameters_dict = {}
        after_render = t.render(parameters_dict)
        resources_template = yaml.safe_load(after_render)
        self.resources_template = resources_template
        if resources_template and u'Resources' in resources_template:
            self._get_instances_configure(resources_template[u'Resources'])

    def _get_instances_configure(self, resources):
        for name in resources:
            body = resources[name]
            t = body[u'Type']
            number = body[u'Number']
            if number <= 0:
                continue
            if t == u'InstanceGroup':
                self._get_instances_configure(body[u'Members'])
            elif t == u'Instance':
                self.instances_stack.append(name)
            else:
                raise Exception(u'unknown type: %s' % t)

    def _launch_resources(self, resources, parent):
        for name in resources:
            body = resources[name]
            t = body[u'Type']
            number = body[u'Number']
            if number <= 0:
                continue
            if t ==u'InstanceGroup':
                for i in range(0, number):
                    uuid = u'%s/%s:%d' % (parent, name, i)
                    self._launch_resources(body[u'Members'], uuid)
            elif t == u'Instance':
                for i in range(0, number):
                    uuid = u'%s/%s:%d' % (parent, name, i)
                    vendor = self.vendor
                    region = self.region
                    profiles_dict = self.conf_dict[u'Instances'][name]
                    profiles = []
                    for item in profiles_dict:
                        real_name = item[len(name)+1:]
                        value = profiles_dict[item]
                        profile = {}
                        profile[u'Name'] = real_name
                        profile[u'Value'] = value
                        profiles.append(profile)
                    specialisms = self.conf_dict[u'Specialisms']
                    launch_instance(uuid, profiles, self.stack_name, vendor, region, specialisms)
            else:
                raise Exception(u'unknown type: %s' % t)