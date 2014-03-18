#! /usr/bin/env python

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
import time
from api_client import ApiV1Client
import clin_lib

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
class PseudoArgs():
    pass

def load_remote_template_file(service_name, clin_default_dir):
    args = PseudoArgs()
    args.clin_default_dir = clin_default_dir
    args.packagename = service_name
    args.versionnumber = u'last'
    download_dir = u'/tmp/.clin/'
    args.path = download_dir
    clin_download(args)
    return u'%s%s-last' % (download_dir, service_name)

def load_template(service_name, clin_default_dir):
    local_flag = u'file://'
    length = len(local_flag)
    if service_name[0:length] == local_flag:
        return service_name[length:]
    else:
        return load_remote_template_file(service_name, clin_default_dir)

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

def clin_create(args):
    clin_default_dir = get_default_dir(args)
    packagename = args.packagename
    username = args.username
    password = args.password
    apiserver = None
    conf_path = u'%s/conf.yml' % clin_default_dir
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
            if not username:
                if u'username' in t:
                    username = t[u'username']
            if not password:
                if u'password' in t:
                    password = t[u'password']
                elif u'password_base64' in t:
                    password = base64.decodestring(t[u'password_base64'])
    if not apiserver:
        apiserver = default_api_server
    if not username:
        username = raw_input(u'username:')
    if not password:
        password = getpass.getpass(u'Enter password:')
    client = ApiV1Client(apiserver)
    ret = client.create_package(username, password, packagename)
    print(ret)

def clin_upload(args):
    clin_default_dir = get_default_dir(args)
    packagename = args.packagename
    versionnumber = args.versionnumber
    description = args.description
    path = args.path
    username = args.username
    password = args.password
    apiserver = None
    conf_path = u'%s/conf.yml' % clin_default_dir
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
            if not username:
                if u'username' in t:
                    username = t[u'username']
            if not password:
                if u'password' in t:
                    password = t[u'password']
                elif u'password_base64' in t:
                    password = base64.decodestring(t[u'password_base64'])
    if not apiserver:
        apiserver = default_api_server
    if not username:
        username = raw_input(u'username:')
    if not password:
        password = getpass.getpass(u'Enter password:')
    if path[-1] == u'/':
        path = path[0:-1]
    filepath = path+u'.zip'
    zip_dir(path, filepath)
    client = ApiV1Client(apiserver)
    ret = client.create_version(username, password, packagename, versionnumber, description, filepath)
    os.remove(filepath)
    print(ret)

def clin_delete(args):
    clin_default_dir = get_default_dir(args)
    packagename = args.packagename
    versionnumber = args.versionnumber
    username = args.username
    password = args.password
    apiserver = None
    conf_path = u'%s/conf.yml' % clin_default_dir
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
            if not username:
                if u'username' in t:
                    username = t[u'username']
            if not password:
                if u'password' in t:
                    password = t[u'password']
                elif u'password_base64' in t:
                    password = base64.decodestring(t[u'password_base64'])
    if not apiserver:
        apiserver = default_api_server
    if not username:
        username = raw_input(u'username:')
    if not password:
        password = getpass.getpass(u'Enter password:')

    client = ApiV1Client(apiserver)
    if versionnumber:
        ret = client.delete_version(username, password, packagename, versionnumber)
    else:
        ret = client.delete_package(username, password, packagename)
    print(ret)

def clin_list(args):
    clin_default_dir = get_default_dir(args)
    packagename = args.packagename
    versionnumber = args.versionnumber
    username = args.username
    allusers = args.allusers
    apiserver = None
    conf_path = u'%s/conf.yml' % clin_default_dir
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
    if not apiserver:
        apiserver = default_api_server

    client = ApiV1Client(apiserver)
    if allusers == u'yes':
        ret = client.get_users()
    elif username:
        ret = client.get_packages(username)
    elif packagename:
        ret = client.get_all_packages(packagename)
        username = ret[0][u'username']
        if versionnumber:
            ret = client.get_version(username, packagename, versionnumber)
        else:
            ret = client.get_versions(username, packagename)
    else:
        ret = client.get_all_packages()
    print(ret)

def clin_download(args):
    clin_default_dir = get_default_dir(args)
    packagename = args.packagename
    versionnumber = args.versionnumber
    download_dir = args.path
    if not versionnumber:
        versionnumber = u'last'

    apiserver = None
    conf_path = u'%s/conf.yml' % clin_default_dir
    if os.path.exists(conf_path):
        with open(conf_path, u'r') as f:
            t = yaml.safe_load(f)
        if u'apiserver' in t:
            apiserver = t[u'apiserver']
    if not apiserver:
        apiserver = default_api_server

    client = ApiV1Client(apiserver)
    ret = client.get_all_packages(packagename)
    username = ret[0][u'username']
    ret = client.get_version(username, packagename, versionnumber)
    download_link = ret[u'link']
    r=urllib2.urlopen(download_link)
    if not download_dir:
        download_dir = u'./'
    elif download_dir[-1] != u'/':
        download_dir = download_dir + u'/'
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)
    service_name = u'%s-%s' % (packagename, versionnumber)
    download_name = service_name + u'.zip'
    f=open(download_dir + download_name, u'wb')
    f.write(r.read())
    f.close()
    if os.path.exists(download_dir+service_name):
        shutil.rmtree(download_dir+service_name)
    unzip_file(download_dir+download_name, download_dir+service_name)
    os.remove(download_dir + download_name)

def get_string_input(name, allowed_values, max_value, min_value):
    prompt = u'%s:\n' % name
    if allowed_values:
        prompt = u'%sselect a number\n' % prompt
        index = 0
        for allowed_value in allowed_values:
            item = u'%d %s\n' % (index, allowed_value)
            prompt = u'%s%s' % (prompt, item)
            index += 1
    elif max_value and min_value:
        item = u'max: %s min: %s\n' % (max_value, min_value)
        prompt = u'%s%s' % (prompt, item)
    elif max_value:
        item = u'max: %s\n' % max_value
        prompt = u'%s%s' % (prompt, item)
    elif min_value:
        item = u'min: %s\n' % min_value
        prompt = u'%s%s' % (prompt, item)
    while True:
        inp = raw_input(prompt)
        if allowed_values or max_value or min_value:
            try:
                inp = int(inp)
            except Exception, e:
                continue
        if allowed_values:
            if inp < 0 or inp >= len(allowed_values):
                continue
            else:
                inp = allowed_values[inp]
                return inp
        if max_value:
            if inp > max_value:
                continue
        if min_value:
            if inp < min_value:
                continue
        return unicode(inp)

def get_boolean_input(name):
    prompt = u'Enable %s (y/n):' % name
    while True:
        inp = raw_input(prompt)
        if inp not in [u'y', u'n']:
            continue
        elif inp == u'y':
            inp = True
        else:
            inp = False
        return inp

def get_list_input(name, allowed_values, max_value, min_value):
    prompt = u'%s:\n' % name
    if allowed_values:
        prompt = u'%sselect items by number, and divide by blank\n' % prompt
        index = 0
        for allowed_value in allowed_values:
            item = u'%d %s\n' % (index, allowed_value)
            prompt = u'%s%s' % (prompt, item)
            index += 1
    while True:
        inp = raw_input(prompt)
        values = []
        if allowed_values:
            items = inp.split(u' ')
            has_error = False
            for item in items:
                if not item:
                    continue
                try:
                    index = int(item)
                except Exception, e:
                    has_error = True
                    break
                if index < 0 or index >= len(allowed_values):
                    has_error = True
                    break
                values.append(allowed_values[index])
            if has_error:
                continue
            else:
                return values

def get_profiles_from_user(profiles):
    for profile in profiles:
        name = profile[u'Name']
        t = profile[u'Type']
        if u'AllowedValues' in profile:
            allowed_values = profile[u'AllowedValues']
        else:
            allowed_values = None
        if u'MaxValue' in profile:
            max_value = profile[u'MaxValue']
        else:
            max_value = None
        if u'MinValue' in profile:
            min_value = profile[u'MinValue']
        else:
            min_value = None
        if t == u'String':
            inp = get_string_input(name, allowed_values, max_value, min_value)
            profile[u'Value'] = inp
        elif t == u'Boolean':
            inp = get_boolean_input(name)
            profile[u'Value'] = inp
        elif t == u'List':
            inp = get_list_input(name, allowed_values, max_value, min_value)
            profile[u'Value'] = inp
        else:
            raise Exception(u'invalid type: %s' % t)

def clin_deploy(args):
    clin_default_dir = get_default_dir(args)

    service_dir = load_template(args.name, clin_default_dir)

    if args.debug == 'yes':
        debug = True
    else:
        debug = False
    deploy = clin_lib.Deploy(service_dir, args.stack_name, args.vendor, args.region, \
                                 args.configure_file, args.use_compile, clin_default_dir, debug)
    while True:
        profiles = deploy.get_next()
        if not profiles:
            break
        while True:
            get_profiles_from_user(profiles)
            ret = deploy.set_profiles(profiles)
            if ret:
                print(ret)
                continue
            else:
                break
    if args.dump_configure in (u'yes', u'only'):
        configure_dict =deploy.get_configure()
        file_name = u'%s-%s.yml' % (args.stack_name, int(time.time()))
        with open(file_name, u'w') as f:
            yaml.safe_dump(configure_dict, f)
        if args.dump_configure == u'only':
            return
    print('launch_resources')
    deploy.launch_resources()
    print('launching')
    while not deploy.is_complete():
        time.sleep(1)
        messages = deploy.get_new_messages()
        for message in messages:
            print(message)
    messages = deploy.get_new_messages()
    for message in messages:
        print(message)
    outputs = deploy.get_output()
    print(u'Outputs:')
    for output in outputs:
        print(output)

def clin_erase(args):
    clin_default_dir = get_default_dir(args)
    clin_lib.Erase(args.stack_name, args.vendor, args.region, clin_default_dir)

def main():
    parser = argparse.ArgumentParser(prog=u'clin', add_help=True)
    import __init__
    parser.add_argument(u'-v', u'--version', action=u'version', version=__init__.__version__)

    subparsers = parser.add_subparsers(help='sub-command help')

    parser_deploy = subparsers.add_parser(u'deploy', help=u'deploy a service to a cloud platform')
    parser_deploy.add_argument(u'name', help=u'service name, if start with file:// while be consider as local package')
    parser_deploy.add_argument(u'--vendor', help=u'the cloud platform vendor')
    parser_deploy.add_argument(u'--region', help=u'region of the vendor')
    parser_deploy.add_argument(u'--stack-name', required=True, \
                                   help=u'the stack name of the service, \
shoud be unique per vendor per region')
    parser_deploy.add_argument(u'--configure-file', \
                                   help=u'yaml format file for the deploied service configuration')
    parser_deploy.add_argument(u'--dump-configure', choices=(u'yes', u'no', u'only'), default=u'no', \
                                   help=u'yes meams dump configure to current directory,\
no means do not dump configure,\
only means only dump configure file, do not do actual deploy')
    parser_deploy.add_argument(u'--use-compile', \
                                   help=u'use compile', \
                                   choices=(u'yes', u'no', u'auto'), default=u'no')
    parser_deploy.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_deploy.add_argument(u'--debug', \
                                   help=u'show debug information when deploy',
                               choices=(u'yes', u'no'), default=u'no')
    parser_deploy.set_defaults(func=clin_deploy)

    parser_erase = subparsers.add_parser('erase', help='erase a service from a cloud platform')
    parser_erase.add_argument('--vendor', help='the cloud platform vendor', required=True)
    parser_erase.add_argument(u'--region', help=u'region of the vendor', required=True)
    parser_erase.add_argument(u'--stack-name', required=True, \
                                  help=u'the stack name of the service, \
shoud be unique per vendor per region')
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

    parser_create = subparsers.add_parser(u'create', help=u'create a package on api server')
    parser_create.add_argument(u'--packagename', help=u'the package name you want to create', required=True)
    parser_create.add_argument(u'--username', help=u'user name of the package owner')
    parser_create.add_argument(u'--password', help=u'password of the user')
    parser_create.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_create.set_defaults(func=clin_create)

    parser_upload = subparsers.add_parser(u'upload', help=u'upload a specific version of a package')
    parser_upload.add_argument(u'--packagename', help=u'the package name for this version', required=True)
    parser_upload.add_argument(u'--versionnumber', help=u'the version number you want to upload, should be int or float', required=True)
    parser_upload.add_argument(u'--description', help=u'a short description', required=True)
    parser_upload.add_argument(u'--path', help=u'the directory path of this package version', required=True)
    parser_upload.add_argument(u'--username', help=u'user name of this package and version owner')
    parser_upload.add_argument(u'--password', help=u'password of the user')
    parser_upload.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_upload.set_defaults(func=clin_upload)

    parser_delete = subparsers.add_parser(u'delete', help=u'delete a specific version of a package or delete a package')
    parser_delete.add_argument(u'--packagename', help=u'package name you want to delete, should only delete a package after delete all the versions', required=True)
    parser_delete.add_argument(u'--versionnumber', help=u'the specific version you want to delete')
    parser_delete.add_argument(u'--username', help=u'user name')
    parser_delete.add_argument(u'--password', help=u'password')
    parser_delete.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_delete.set_defaults(func=clin_delete)

    parser_list = subparsers.add_parser(u'list', help=u'list packages, versions, or users')
    parser_list.add_argument(u'--packagename', help=u'if specific, list the specific package')
    parser_list.add_argument(u'--versionnumber', help=u'if specific, list the specific version of the specific package')
    parser_list.add_argument(u'--username', help=u'if specific, list the packages belong to the specific user')
    parser_list.add_argument(u'--allusers', help=u'if set to yes, list all the users')
    parser_list.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_list.set_defaults(func=clin_list)

    parser_download = subparsers.add_parser(u'download', help=u'download package to local')
    parser_download.add_argument(u'--packagename', help=u'package want to download', required=True)
    parser_download.add_argument(u'--versionnumber', help=u'version want to download, if not specific, download the last version')
    parser_download.add_argument(u'--path', help=u'local directory to download')
    parser_download.add_argument(u'--clin-default-dir', help=u'the default directory for configure file of clin program')
    parser_download.set_defaults(func=clin_download)

    args = parser.parse_args()
    args.func(args)

if __name__ == u'__main__':
    main()
