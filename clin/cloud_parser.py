#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import os
import yaml
import urllib2
import zipfile
import shutil
import requests
import argparse
import getpass
import base64
from parsing_version_1 import DeployVersion1, EraseVersion1
from api_client import ApiV1Client

def zip_dir(dirname,zipfilename):
    filelist = []
    if os.path.isfile(dirname):
        filelist.append(dirname)
    else :
        for root, dirs, files in os.walk(dirname):
            for name in files:
                filelist.append(os.path.join(root, name))

    zf = zipfile.ZipFile(zipfilename, "w", zipfile.zlib.DEFLATED)
    for tar in filelist:
        arcname = tar[len(dirname):]
        #print arcname
        zf.write(tar,arcname)
    zf.close()

def unzip_file(zipfilename, unziptodir):
    if not os.path.exists(unziptodir): os.mkdir(unziptodir, 0777)
    zfobj = zipfile.ZipFile(zipfilename)
    for name in zfobj.namelist():
        name = name.replace('\\','/')
        if name.endswith('/'):
            os.mkdir(os.path.join(unziptodir, name))
        else:
            ext_filename = os.path.join(unziptodir, name)
            ext_dir= os.path.dirname(ext_filename)
            if not os.path.exists(ext_dir) : os.mkdir(ext_dir,0777)
            outfile = open(ext_filename, 'wb')
            outfile.write(zfobj.read(name))
            outfile.close()

url_prefix = u'http://cloudinstall.yupeng820921.tk'
download_prefix = url_prefix + u'/download/'
def load_remote_template_file(service_name):
    url = download_prefix + service_name
    request = urllib2.Request(url)
    opener = urllib2.build_opener()
    download_link = opener.open(request).read()
    r=urllib2.urlopen(download_link)
    download_dir = u'/tmp/.clin/'
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)
    download_name = service_name + u'.zip'
    f=open(download_dir + download_name, u'wb')
    f.write(r.read())
    f.close()
    if os.path.exists(download_dir+service_name):
        shutil.rmtree(download_dir+service_name)
    unzip_file(download_dir+download_name, download_dir+service_name)
    return download_dir+service_name

def load_template(service_name):
    local_flag = u'file://'
    length = len(local_flag)
    if service_name[0:length] == local_flag:
        return service_name[length:]
    else:
        return load_remote_template_file(service_name)

# def clin_upload(args):
#     package_dir = args.package_dir
#     if package_dir[-1] == u'/':
#         package_dir = package_dir[0:-1]
#     package_name = package_dir.rsplit('/')[-1]
#     zip_dir(package_dir, package_dir+u'.zip')
#     files = {'packagefile': (package_name+u'.zip', open(package_dir+u'.zip', 'rb'))}
#     url = url_prefix + u'?action=upload'
#     r = requests.post(url, files=files)
#     os.remove(package_dir+u'.zip')

def get_default_dir(args):
    clin_default_dir = args.clin_default_dir
    if not clin_default_dir:
        if u'HOME' in os.environ:
            home = os.environ['HOME']
        else:
            home = os.getcwd()
        clin_default_dir = home + u'/.clin'
    return clin_default_dir

default_api_server = u'https://apitest.yupeng820921.tk'
def clin_register(args):
    clin_default_dir = get_default_dir(args)
    conf_path = u'%s/conf.yml' % clin_default_dir
    apiserver = None
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
    if not apiserver:
        apiserver = default_api_server
    username = args.username
    password = args.password
    if not password:
        while True:
            pw1 = getpass.getpass(u'Enter password:')
            if len(pw1) < 3:
                print(u'passworld should more than 3 characters')
                continue
            pw2 = getpass.getpass(u'Confirm password:')
            if pw1 != pw2:
                print(u'confirm incorrect')
                continue
            password = pw1
            break
    client = ApiV1Client(apiserver)
    ret = client.create_user(username, password)
    print(ret)
    print(base64.encodestring(password))

def clin_unregister(args):
    clin_default_dir = get_default_dir(args)
    username = args.username
    password = args.password
    apiserver = None
    conf_path = u'%s/conf.yml' % clin_default_dir
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
        if not password:
            if u'password' in t:
                password = t[u'password']
            elif u'password_base64' in t:
                password = base64.decodestring(t[u'password_base64'])
    if not apiserver:
        apiserver = default_api_server
    if not password:
        password = getpass.getpass(u'Enter password:')
    client = ApiV1Client(apiserver)
    ret = client.delete_user(username, password)
    print(ret)

def clin_deploy(args):
    clin_default_dir = get_default_dir(args)

    template_dir = load_template(args.name)

    with open(u'%s/init.yml' % template_dir, u'r') as f:
        first_line = f.next()
        t = yaml.safe_load(first_line)
        if u'Version' not in t:
            raise Exception(u'Version not found')
        v = t[u'Version']
    if v == 1:
        DeployVersion1(template_dir, args.stack_name, args.productor, args.region, args.configure_file, \
                               args.use_default, args.dump_configure, clin_default_dir)
    else:
        raise Exception(u'unsupport version: %s' % v)

def clin_erase(args):
    clin_default_dir = get_default_dir(args)
    EraseVersion1(args.stack_name, args.productor, args.region, clin_default_dir)

def main():
    parser = argparse.ArgumentParser(prog=u'clin', add_help=True)
    import __init__
    parser.add_argument(u'-v', u'--version', action=u'version', version=__init__.__version__)

    subparsers = parser.add_subparsers(help='sub-command help')

    parser_deploy = subparsers.add_parser(u'deploy', help=u'deploy a service to a cloud platform')
    parser_deploy.add_argument(u'name', help=u'service name, if start with file:// while be consider as local package')
    parser_deploy.add_argument(u'--productor', help=u'the cloud platform vendor')
    parser_deploy.add_argument(u'--region', help=u'region of the productor')
    parser_deploy.add_argument(u'--stack-name', required=True, \
                                   help=u'the stack name of the service, \
shoud be unique per productor per region')
    parser_deploy.add_argument(u'--configure-file', \
                                   help=u'yaml format file for the deploied service configuration')
    parser_deploy.add_argument(u'--dump-configure', choices=(u'yes', u'no', u'only'), default=u'no', \
                                   help=u'yes meams dump configure to current directory,\
no means do not dump configure,\
only means only dump configure file, do not do actual deploy')
    parser_deploy.add_argument(u'--use-default', choices=(u'yes', u'no'), default=u'no', \
                                   help=u'whether use package default value')
    parser_deploy.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_deploy.set_defaults(func=clin_deploy)

    parser_erase = subparsers.add_parser('erase', help='erase a service from a cloud platform')
    parser_erase.add_argument('--productor', help='the cloud platform vendor')
    parser_erase.add_argument(u'--region', help=u'region of the productor')
    parser_erase.add_argument(u'--stack-name', required=True, \
                                  help=u'the stack name of the service, \
shoud be unique per productor per region')
    parser_erase.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_erase.set_defaults(func=clin_erase)

    parser_register = subparsers.add_parser(u'register', help=u'register a user to api server')
    parser_register.add_argument(u'--username', help=u'user name, should larger than 3 characters', required=True)
    parser_register.add_argument(u'--password', help=u'password, should larger than 3 characters')
    parser_register.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_register.set_defaults(func=clin_register)

    parser_unregister = subparsers.add_parser(u'unregister', help=u'unregister a user')
    parser_unregister.add_argument(u'--username', help=u'user name want to unregister', required=True)
    parser_unregister.add_argument(u'--password', help=u'passord for the user')
    parser_unregister.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_unregister.set_defaults(func=clin_unregister)

    # parser_create = subparsers.add_parser(u'create', help=u'create a package on api server')
    # parser_create.add_argument(u'--packagename', help=u'the package name you want to create', required=True)
    # parser_create.add_argument(u'--username', help=u'user name of the package owner')
    # parser_create.add_argument(u'--password', help=u'password of the user')
    # parser_create.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    # parser_create.set_defaults(func=clin_create)

    # parser_upload = subparsers.add_parser(u'upload', help=u'upload a specific version of a package')
    # parser_upload.add_argument(u'--packagename', help=u'the package name for this version', required=True)
    # parser_upload.add_argument(u'--versionnumber', help=u'the version number you want to upload, should be int or float', required=True)
    # parser_upload.add_argument(u'--path', help=u'the directory path of this package version', required=True)
    # parser_upload.add_argument(u'--username', help=u'user name of this package and version owner')
    # parser_upload.add_argument(u'--password', help=u'password of the user')
    # parser_upload.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    # parser_upload.set_defaults(func=clin_upload)

    # parser_delete = usbparsers.add_parser(u'delete', help=u'delete a specific version of a package or delete a package')
    # parser_delete.add_argument(u'--packagename', help=u'package name you want to delete, should only delete a package after delete all the versions', required=True)
    # parser_delete.add_argument(u'--versionnumber', help=u'the specific version you want to delete')
    # parser_delete.add_argument(u'--username', help=u'user name')
    # parser_delete.add_argument(u'--password', help=u'password')
    # parser_delete.set_defaults(func=clin_delete)

    args = parser.parse_args()
    args.func(args)

if __name__ == u'__main__':
    main()
