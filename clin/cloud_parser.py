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
from parsing_version_1 import DeployVersion1, EraseVersion1

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

def clin_upload(args):
    package_dir = args.package_dir
    if package_dir[-1] == u'/':
        package_dir = package_dir[0:-1]
    package_name = package_dir.rsplit('/')[-1]
    zip_dir(package_dir, package_dir+u'.zip')
    files = {'packagefile': (package_name+u'.zip', open(package_dir+u'.zip', 'rb'))}
    url = url_prefix + u'?action=upload'
    r = requests.post(url, files=files)
    os.remove(package_dir+u'.zip')

def clin_deploy(args):

    clin_default_dir = args.clin_default_dir
    if not clin_default_dir:
        if u'HOME' in os.environ:
            clin_default_dir = os.environ['HOME']
        else:
            clin_default_dir = os.getcwd()
    clin_default_dir = clin_default_dir + u'/.clin'

    template_dir = load_template(args.name)

    with open(u'%s/init.yml' % template_dir, u'r') as f:
        first_line = f.next()
        t = yaml.safe_load(first_line)
        if u'Version' not in t:
            raise Exception(u'Version not found')
        v = t[u'Version']
    if v == 1:
        DeployVersion1(template_dir, args.stack_name, args.productor, args.region, args.configure_file, \
                               args.use_default, args.dump_configure, args.clin_default_dir)
    else:
        raise Exception(u'unsupport version: %s' % v)

def clin_erase(args):

    if not clin_default_dir:
        if u'HOME' in os.environ:
            clin_default_dir = os.environ['HOME']
        else:
            clin_default_dir = os.getcwd()
    clin_default_dir = clin_default_dir + u'/.clin'

    EraseVersion1(args.stack_name, args.productor, args.region, args.clin_default_dir)

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

    parser_upload = subparsers.add_parser(u'upload', help=u'upload package to cloud install web site')
    parser_upload.add_argument(u'package_dir', help=u'the local directory of the package')
    parser_upload.set_defaults(func=clin_upload)

    args = parser.parse_args()
    args.func(args)

if __name__ == u'__main__':
    main()
