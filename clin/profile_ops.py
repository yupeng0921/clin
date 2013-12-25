#! /usr/bin/env python

def generate_profile(name, t, description, allowed_values=None, max_value=None, min_value=None):
    profile = {}
    profile[u'Name'] = name
    profile[u'Type'] = t
    profile[u'Description'] = description
    profile[u'AllowedValues'] = allowed_values
    profile[u'MaxValue'] = max_value
    profile[u'MinValue'] = min_value
    return profile

def verify_profile(profile):
    value = profile[u'Value']
    if profile[u'Type'] == u'List':
        if type(value) is not types.ListType:
            return u'should input a list'
        allowed_values = profile[u'AllowedValues']
        if allowed_values:
            for v in value:
                if v not in allowed_values:
                    return u'%s not in allowed values' % v
    elif profile[u'Type'] == u'String':
        if u'AllowedValues' in profile:
            allowed_values = profile[u'AllowedValues']
        else:
            allowed_values = None
        if allowed_values:
            if value not in allowed_values:
                return u'%s not in allowed values' % value
        if u'MaxValue' in profile:
            max_value = profile[u'MaxValue']
        else:
            max_value = None
        if u'MinValue' in profile:
            min_value = profile[u'MinValue']
        else:
            min_value = None
        if max_value or min_value:
            try:
                value = int(value)
            except Exception, e:
                return u'%s is not a number' % value
        if max_value:
            if value > max_value:
                return u'%s is larger than %s' % (value, max_value)
        if min_value:
            if value < min_value:
                return u'%s is smaller than %s' % (value, min_value)
    return None
