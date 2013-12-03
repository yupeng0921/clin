#! /usr/bin/env python

import requests
import json

class ClinRequests():
    @staticmethod
    def __verify_and_close(rep):
        rep.close()
        if rep.ok:
            return
        try:
            js = rep.json()
        except Exception, e:
            has_js = False
        else:
            has_js = True
        if has_js:
            raise Exception(json.dumps(js))
        else:
            rep.raise_for_status()

    @staticmethod
    def get(*k, **kw):
        rep = requests.get(*k, **kw)
        ClinRequests.__verify_and_close(rep)
        return rep.json()

    @staticmethod
    def post(*k, **kw):
        rep = requests.post(*k, **kw)
        ClinRequests.__verify_and_close(rep)
        return rep.json()

    @staticmethod
    def delete(*k, **kw):
        rep = requests.delete(*k, **kw)
        ClinRequests.__verify_and_close(rep)
        return rep.json()

class ApiV1Client():
    def __init__(self, endpoint):
        js = ClinRequests.get(endpoint, verify=False)
        v1 = js[u'v1']
        self.base = u'%s%s' % (endpoint, v1)

    def get_users(self):
        url = u'%s/users' % self.base
        js = ClinRequests.get(url, verify=False)
        return js

    def create_user(self, username, password):
        url = u'%s/users' % self.base
        headers = {'content-type': 'application/json'}
        data = {u'username':username, u'password':password}
        data = json.dumps(data)
        js = ClinRequests.post(url, data=data, headers=headers, verify=False)
        return js

    def delete_user(self, username, password):
        url = u'%s/users/%s' % (self.base, username)
        auth = (username, password)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.delete(url, headers=headers, auth=auth, verify=False)
        return js

    def create_package(self, username, password, packagename):
        url = u'%s/users/%s' % (self.base, username)
        auth=(username, password)
        headers = {'content-type': 'application/json'}
        data = {u'packagename': packagename}
        data = json.dumps(data)
        js = ClinRequests.post(url, data=data, headers=headers, auth=auth, verify=False)
        return js

    def get_packages(self, username):
        url = u'%s/users/%s' % (self.base, username)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.get(url, headers=headers, verify=False)
        return js

    def delete_package(self, username, password, packagename):
        url = u'%s/users/%s/%s' % (self.base, username, packagename)
        auth = (username, password)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.delete(url, headers=headers, auth=auth, verify=False)
        return js

    def create_version(self, username, password, packagename, versionnumber, description, filepath):
        url = u'%s/users/%s/%s' % (self.base, username, packagename)
        auth = (username, password)
        headers = {}
        headers[u'Content-Type'] = u'application/octet-stream'
        headers[u'X-versionnumber'] = versionnumber
        headers[u'X-description'] = description
        with open(filepath, u'rb') as f:
            js = ClinRequests.post(url, data=f, headers=headers, auth=auth, verify=False)
        return js

    def get_versions(self, username, packagename):
        url = u'%s/users/%s/%s' % (self.base, username, packagename)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.get(url, headers=headers, verify=False)
        return js

    def get_version(self, username, packagename, versionnumber):
        url = u'%s/users/%s/%s/%s' % (self.base, username, packagename, versionnumber)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.get(url, headers=headers, verify=False)
        return js

    def delete_version(self, username, password, packagename, versionnumber):
        url = u'%s/users/%s/%s/%s' % (self.base, username, packagename, versionnumber)
        auth = (username, password)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.delete(url, headers=headers, auth=auth, verify=False)
        return js

    def get_all_packages(self):
        url = u'%s/packages' % (self.base)
        headers = {'content-type': 'application/json'}
        js = ClinRequests.get(url, headers=headers, verify=False)
        return js

if __name__ == u'__main__':
    client = ApiV1Client(u'https://apitest.yupeng820921.tk')
    username = u'hank'
    password = u'123'
    packagename = u'packageA'
    versionnumber = u'0.1'
    description = u'example package'
    filepath = u'/tmp/example.zip'

    ret = client.create_user(username, password)

    ret = client.get_users()
    print(ret)

    ret = client.create_package(username, password, packagename)

    ret = client.get_packages(username)
    print(ret)

    ret = client.create_version(username, password, packagename, versionnumber, description, filepath)

    ret = client.get_versions(username, packagename)
    print(ret)

    ret = client.get_version(username, packagename, versionnumber)
    print(ret)

    ret = client.get_all_packages()
    print(ret)

    ret = client.delete_version(username, password, packagename, versionnumber)

    ret = client.delete_package(username, password, packagename)

    ret = client.delete_user(username, password)

    ret = client.get_users()
    print(ret)
