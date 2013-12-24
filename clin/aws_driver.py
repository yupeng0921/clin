#! /usr/bin/env python

import boto

class Driver():
    def get_regions(self):
        regions = [u'us-east-1', u'us-west-1', u'us-west-2', \
                       u'eu-west-1', u'ap-southeast-1', u'ap-southeast-2', \
                       u'ap-northeast-1', u'sa-east-1']
        return regions
    def get_specialism(self):
        return None
    def verify_specialism(self, profiles, vendor):
        return None
    def get_instance_profiles(self):
        profile = {}
        profile[u'Name'] = u'instance type'
        profile[u'Description'] = u'instance type'
        profile[u'Type'] = u'String'
        profile[u'AllowedValues'] = [u't1.micra', u'm1.small']
        return [profile]
    def verify_instance_profiles(self, profiles):
        return None
    def create_keypair(self, keypair_name, region):
        return None
    def launch_instance(self, uuid, profiles, \
                            keypair_name, region):
        print(uuid)

driver = Driver()
