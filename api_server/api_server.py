#! /usr/bin/env python

from flask import Flask, request, url_for, json, abort, Response
import boto
import boto.s3
from boto.s3.key import Key
import pymongo
import time
import hashlib
import types
import os
import shutil

app = Flask(__name__)

link = u'https://api.cloudinstall.yupeng820921.tk'

class Backend():
    def __init__(self):
        client = pymongo.MongoClient('localhost', 27017)
        db = client.ciapi
        self.db = db
        self.packages = db.packages
        self.users = db.users
        self.uuid = db.uuid
        conn = boto.s3.connect_to_region(u'us-west-2')
        self.bucket = conn.get_bucket(u'cloudinstall')
        self.link_prefix = u'https://s3-us-west-2.amazonaws.com/cloudinstall'

    def create_user(self, username, password):
        user = {
            u'_id': username,
            u'password': password,
            u'packages': {}
            }
        try:
            self.users.insert(user)
        except pymongo.mongo_client.DuplicateKeyError, e:
            return u'user exist'
        return None

    def delete_user(self, username):
        ret = self.users.remove({u'_id':username, u'packages': {}})
        if ret[u'n'] != 1:
            return u'delete users number: %d' % ret[u'n']
        return None

    def get_password(self, username):
        ret = self.users.find_one({u'_id':username}, {u'password':1})
        if not ret:
            return u'user not found'
        if u'password' not in ret:
            return u'internal error, password not found'
        return (username, ret[u'password'])

    def get_users(self):
        ret = self.users.find()
        users_list = []
        for user in ret:
            users_list.append(user['_id'])
        return users_list

    def create_package(self, username, packagename):
        package = {u'_id':packagename, u'username':username}
        try:
            self.packages.insert(package)
        except pymongo.mongo_client.DuplicateKeyError, e:
            return u'packages exist'
        item = u'packages.%s' % packagename
        ret = self.users.update({u'_id':username, item:{u'$exists':False}}, {u'$set':{item:[]}})
        if ret[u'updatedExisting'] != True or ret[u'err'] != None or ret[u'n'] != 1:
            self.packages.remove({u'_id':packagename})
            return json.dumps(ret)
        return None

    def delete_package(self, username, packagename):
        item = u'packages.%s' % packagename
        ret = self.users.update({u'_id':username, item:{u'$in':[[]]}}, {u'$unset':{item:1}})
        # the package may be deleted by previous delete, so only check err
        if ret[u'err'] != None:
            return json.dumps(ret)
        ret = self.packages.remove({u'_id':packagename})
        if ret[u'err'] != None or ret[u'n'] != 1:
            return json.dumps(ret)
        return None

    def get_packages_by_user(self, username):
        ret = self.users.find_one({u'_id':username}, {u'packages':1})
        if not ret:
            return u'user not found'
        if u'packages' not in ret:
            return u'internal error, packages not found'
        return ret[u'packages'].keys()

    def create_version(self, username, packagename, versionnumber, info, filepath):
        version = dict({u'versionnumber': versionnumber, u'status': u'pre-upload'}, **info)
        item = u'packages.%s' % packagename
        item_v = u'%s.versionnumber' % item
        ret = self.users.update({u'_id': username, \
                                     item: {u'$exists': True}, \
                                     item_v: {u'$ne': versionnumber}}, \
                                    {u'$push': {item: version}})
        if ret[u'updatedExisting'] != True or ret[u'err'] != None or ret[u'n'] != 1:
            return json.dumps(ret)
        k = Key(self.bucket)
        k.key = u'%s-%s.zip' % (packagename, versionnumber)
        k.set_contents_from_filename(filepath)
        k.set_acl(u'public-read')
        item_s = u'%s.$.status' % item
        ret = self.users.update({u'_id': username, \
                                     item: {u'$exists': True}, \
                                     item_v: versionnumber}, \
                                    {u'$set': {item_s: u'update'}})
        if ret[u'updatedExisting'] != True or ret[u'err'] != None or ret[u'n'] != 1:
            return json.dumps(ret)
        return None

    def delete_version(self, username, packagename, versionnumber):
        k = Key(self.bucket)
        k.key = u'%s-%s.zip' % (packagename, versionnumber)
        k.delete()
        item = u'packages.%s' % packagename
        item_v = u'%s.versionnumber' % item
        ret = self.users.update({u'_id': username, \
                                     item: {u'$exists': True}, \
                                     item_v: versionnumber}, \
                                    {'$pull': {item: {'versionnumber': versionnumber}}})
        if ret[u'updatedExisting'] != True or ret[u'err'] != None or ret[u'n'] != 1:
            return json.dumps(ret)
        return None

    def get_versions(self, username, packagename):
        item = u'packages.%s' % packagename
        item_v = u'%s.versionnumber' % item
        item_s = u'%s.status' % item
        ret = self.users.find_one({u'_id': username, item: {'$exists': True}}, {item_v: 1, item_s: 1})
        if not ret:
            return u'user or package not found'
        if u'packages' not in ret:
            return u'internal error, no packages'
        if packagename not in ret[u'packages']:
            return u'internal error, no %s' % packagename
        versions = ret['packages'][packagename]
        return versions

    def get_version(self, username, packagename, versionnumber):
        item = u'packages.%s' % packagename
        item_v = u'%s.versionnumber' % item
        item_ss = u'%s.$' % item
        ret = self.users.find_one({u'_id': username, \
                                       item: {u'$exists': True}, \
                                       item_v: versionnumber}, \
                                      {item_ss: 1})
        if not ret:
            return u'user or package or version not found'
        if u'packages' not in ret:
            return u'internal error, no packages'
        if packagename not in ret[u'packages']:
            return u'internal error, no %s' % packagename
        version = ret[u'packages'][packagename][0]
        version[u'link'] = u'%s/%s-%s.zip' % (self.link_prefix, packagename, versionnumber)
        return version

    def get_all_packages(self):
        packages = self.packages.find()
        ret_list = []
        for package in packages:
            package[u'packagename'] = package[u'_id']
            package.pop(u'_id')
            ret_list.append(package)
        return ret_list

backend = Backend()

@app.errorhandler(404)
def not_found(error=None):
    message = {
        'status': 404,
        'message': 'Not Found: ' + request.url,
        }
    resp = jsonify(message)
    resp.status_code = 404
    return resp

def make_resp(data, status):
    js = json.dumps(data)
    resp = Response(js, status=status, mimetype='application/json')
    resp.headers['Link'] = link
    return resp

def do_auth(username):
    auth = request.authorization
    if not auth:
        data = {u'reason': u'no authorization'}
        return make_resp(data, 401)
    if username != auth.username:
        data = {u'reason': u'%s can not delete %s'%(auth.username, username)}
        return make_resp(data, 401)
    password = auth.password
    md5 = hashlib.md5()
    md5.update(password)
    pw1 = md5.hexdigest()
    ret = backend.get_password(username)
    if type(ret) in [types.StringType, types.UnicodeType]:
        data = {u'reason': ret}
        return make_resp(data, 400)
    (username, pw2) = ret
    if pw1 != pw2:
        data = {u'reason': 'password incorrect'}
        return make_resp(data, 401)
    return None

@app.route(u'/', methods = [u'GET'] )
def api_root():
    data = {u'v1': u'/v1'}
    return make_resp(data, 200)

@app.route(u'/v1', methods = [u'GET'])
def api_v1():
    prefix = url_for('api_v1')
    data = {
        u'users' : prefix+u'/users',
        u'packages' : prefix+u'/packages'
        }
    return make_resp(data, 200)

@app.route(u'/v1/users', methods = [u'GET', u'POST', u'DELETE'])
def api_users():
    if request.method == u'GET':
        data = backend.get_users()
        return make_resp(data, 200)
    elif request.method == u'POST':
        try:
            data = request.json
        except Exception, e:
            data = {u'reason': u'not json format'}
            return make_resp(data, 400)
        if u'username' not in data:
            data = {u'reason': u'no username'}
            return make_resp(data, 400)
        username = data[u'username']
        if len(username) < 3:
            data = {u'reason': u'username should larger than 3 characters'}
            return make_resp(data, 400)
        if u'password' not in data:
            data = {u'reason': u'no password'}
            return make_resp(data, 400)
        password = data[u'password']
        if len(password) < 3:
            data = {u'reason': u'password should larger than 3 characters'}
            return make_resp(data, 400)
        md5 = hashlib.md5()
        md5.update(password)
        ret = backend.create_user(username, md5.hexdigest())
        if ret:
            data = {u'reason': ret}
            status = 400
        else:
            data = {u'reason': u'success'}
            status = 200
        return make_resp(data, status)
    else:
        data = {u'reason': u'unsupport method'}
        return make_resp(data, 400)

@app.route(u'/v1/users/<username>', methods = [u'GET', u'POST', u'DELETE'])
def api_username(username):
    if request.method == u'GET':
        data = backend.get_packages_by_user(username)
        if type(data) in [types.StringType, types.UnicodeType]:
            data = {u'reason': data}
            return make_resp(data, 400)
        return make_resp(data, 200)
    elif request.method == u'POST':
        try:
            data = request.json
        except Exception, e:
            data = {u'reason': u'not json format'}
            return make_resp(data, 400)
        if u'packagename' not in data:
            data = {u'reason': u'no packagename'}
            return make_resp(data, 400)
        packagename = data[u'packagename']
        ret = backend.create_package(username, packagename)
        if type(ret) in [types.StringType, types.UnicodeType]:
            data = {u'reason': ret}
            return make_resp(data, 400)
        data = {u'reason': u'success'}
        return make_resp(data, 200)
    elif request.method == u'DELETE':
        ret = do_auth(username)
        if ret:
            return ret
        ret = backend.delete_user(username)
        if type(ret) in [types.StringType, types.UnicodeType]:
            data = {u'reason': ret}
            return make_resp(data, 400)
        data = {u'reason': u'success'}
        return make_resp(data, 200)
    else:
        data = {u'reason': u'unsupport method'}
        return make_resp(data, 400)

@app.route(u'/v1/users/<username>/<packagename>', methods = [u'GET', u'POST', u'DELETE'])
def api_packagename(username, packagename):
    if request.method == u'GET':
        data = backend.get_versions(username, packagename)
        if type(data) in [types.StringType, types.UnicodeType]:
            data = {u'reason': data}
            return make_resp(data, 400)
        return make_resp(data, 200)
    elif request.method == u'POST':
        ret = do_auth(username)
        if ret:
            return ret
        if u'X-versionnumber' not in request.headers:
            data = {u'reason': u'no versionnumber'}
            return make_resp(data, 400)
        versionnumber = request.headers[u'X-versionnumber']
        try:
            float(versionnumber)
        except Exception, e:
            data = {u'reason': u'invalid versionnumber'}
            return make_resp(data, 400)
        if u'X-description' not in request.headers:
            data = {u'reason': u'no description'}
            return make_resp(data, 400)
        description = request.headers['X-description']
        retry_count = 0
        while retry_count < 10:
            timestamp = u'%f' % time.time()
            dirname = u'/tmp/clin%s' % timestamp
            try:
                os.mkdir(dirname)
            except Exception, e:
                retry_count += 1
            else:
                break
        if retry_count == 10:
            data = {u'reason': u'create temp dir failed'}
            return make_resp(data, 500)
        filepath = u'%s/f' % dirname
        with open(filepath, 'wb') as f:
            f.write(request.data)
        info = {
            u'description': description,
            u'timestamp': timestamp
            }
        ret = backend.create_version(username, packagename, versionnumber, info, filepath)
        shutil.rmtree(dirname)
        if type(ret) in [types.StringType, types.UnicodeType]:
            data = {u'reason': ret}
            return make_resp(data, 400)
        data = {u'reason': u'success'}
        return make_resp(data, 200)
    elif request.method == u'DELETE':
        ret = do_auth(username)
        if ret:
            return ret
        ret = backend.delete_package(username, packagename)
        if type(ret) in [types.StringType, types.UnicodeType]:
            data = {u'reason': ret}
            return make_resp(data, 400)
        data = {u'reason': u'success'}
        return make_resp(data, 200)
    else:
        data = {u'reason': u'unsupport method'}
        return make_resp(data, 400)

@app.route(u'/v1/users/<username>/<packagename>/<versionnumber>', methods = [u'GET', u'DELETE'])
def api_versionnumber(username, packagename, versionnumber):
    if request.method == u'GET':
        data = backend.get_version(username, packagename, versionnumber)
        if type(data) in [types.StringType, types.UnicodeType]:
            data = {u'reason': data}
            return make_resp(data, 400)
        return make_resp(data, 200)
    elif request.method == u'DELETE':
        ret = do_auth(username)
        if ret:
            return ret
        ret = backend.delete_version(username, packagename, versionnumber)
        if type(ret) in [types.StringType, types.UnicodeType]:
            data = {u'reason': ret}
            return make_resp(data, 400)
        data = {u'reason': u'success'}
        return make_resp(data, 200)
    else:
        data = {u'reason': u'unsupport method'}
        return make_resp(data, 400)

@app.route(u'/v1/packages', methods = [u'GET'])
def api_packages():
    data = backend.get_all_packages()
    if type(data) in [types.StringType, types.UnicodeType]:
        data = {u'reason': data}
        return make_resp(data, 500)
    return make_resp(data, 200)

if __name__ == u'__main__':
    app.run(host=u'0.0.0.0', port=80, debug=True)
