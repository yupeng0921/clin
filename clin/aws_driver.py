#! /usr/bin/env python

from profile_ops import generate_profile, verify_profile

try:
    import boto
    import boto.vpc
    import boto.ec2
except Exception, e:
    have_boto = False
else:
    have_boto = True

class Driver():
    def get_regions(self):
        if not have_boto:
            raise Exception(u'please install boto: pip install boto')
        regions = [u'us-east-1', u'us-west-1', u'us-west-2', \
                       u'eu-west-1', u'ap-southeast-1', u'ap-southeast-2', \
                       u'ap-northeast-1', u'sa-east-1']
        return regions

    def get_specialisms(self, region):
        conn = boto.vpc.connect_to_region(region)
        vpcs = conn.get_all_vpcs()
        allowed_values = []
        for vpc in vpcs:
            allowed_value = u'%s %s' % (vpc.cidr_block, vpc.id)
            allowed_values.append(allowed_value)
        profile = generate_profile(u'vpc', u'String', u'vpc', allowed_values)
        return [profile]

    def verify_specialisms(self, profiles, region):
        return None

    def get_instance_profiles(self, region, specialisms):
        profiles = []

        profile = generate_profile(u'instance type', u'String', 'instance type', [u't1.micro', u'm1.small'])
        profiles.append(profile)

        vpc_id = specialisms[u'vpc'].split(u' ')[1]
        conn = boto.vpc.connect_to_region(region)
        subnets = conn.get_all_subnets(filters=[('vpcId', [vpc_id])])
        allowed_values = []
        for subnet in subnets:
            allowed_value = u'%s %s' % (subnet.cidr_block, subnet.id)
            allowed_values.append(allowed_value)
        profile = generate_profile(u'subnet', u'List', u'subnet', allowed_values)
        profiles.append(profile)

        return profiles

    def verify_instance_profiles(self, profiles, region, specialisms):
        return verify_profile(profiles[0])

    def create_keypair(self, keypair_name, region):
        return None

    def launch_instance(self, uuid, profiles, \
                            keypair_name, region, specialisms):
        print(uuid)
        print(specialisms[u'vpc'])
        for profile in profiles:
            print('%s %s' % (profile['Name'], profile['Value']))
        print('\n')

driver = Driver()
