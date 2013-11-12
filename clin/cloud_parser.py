#! /usr/bin/env python

# -*- coding: utf-8 -*-

import sys
import os
import getopt
import yaml
import urllib2
import zipfile
import shutil
import requests
from parsing_version_1 import DeployVersion1, EraseVersion1

def load_local_template_file(template_dir):
    template_file = u'%s/init.yml' % template_dir
    with open(template_file, 'r') as f:
        template = yaml.safe_load(f)
    return (template, template_dir)

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
    return load_local_template_file(download_dir+service_name)

def load_template(service_name):
    local_flag = u'file://'
    length = len(local_flag)
    if service_name[0:length] == local_flag:
        return load_local_template_file(service_name[length:])
    else:
        return load_remote_template_file(service_name)

sub_commands = {}
def subcmd(name):
    def _subcmd(func):
        sub_commands[name] =func
        def __subcmd(*args, **kwargs):
            ret = func(*args, **kwargs)
            return ret
        return __subcmd
    return _subcmd

@subcmd(u'upload')
def clin_upload(argv):
    package_dir = argv[0]
    if package_dir[-1] == u'/':
        package_dir = package_dir[0:-1]
    package_name = package_dir.rsplit('/')[-1]
    zip_dir(package_dir, package_dir+u'.zip')
    files = {'packagefile': (package_name+u'.zip', open(package_dir+u'.zip', 'rb'))}
    url = url_prefix + u'?action=upload'
    r = requests.post(url, files=files)
    os.remove(package_dir+u'.zip')

@subcmd(u'deploy')
def clin_deploy(argv):

    def deploy_usage():
        print(u'deploy_usage')

    long_params = [u'stack-name=', u'productor=', u'region=', \
                       u'parameter-file=', u'dump-parameter=', \
                       u'yes', u'debug', u'conf-dir']
    try:
        opts, args = getopt.gnu_getopt(argv, u'y', long_params)
    except getopt.GetoptError, e:
        deploy_usage()
        sys.exit(1)

    stack_name = None
    productor = None
    region = None
    parameter_file = None
    conf_dir = None
    region = None
    use_default = False
    debug = False
    dump_parameter = u'no'
    for o, a in opts:
        if o == u'--stack-name':
            stack_name = a
        elif o == u'--productor':
            productor = a
        elif o == u'--parameter-file':
            parameter_file = a
        elif o == u'--region':
            region = a
        elif o == u'-template-file':
            template_file = a
        elif o == u'--dump-parameter':
            if a in (u'no', u'yes', u'only'):
                dump_parameter = a
            else:
                sys.stderr.write(u'invalid dump-parameter: %s, should be no, yes, only\n' % a)
                sys.exit(1)
        elif o in (u'-y', '--yes'):
            use_default = True
        elif o == u'--conf-dir':
            conf_dir = a
        elif o == u'--debug':
            debug = True
        else:
            sys.stderr.write(u'invalid args: %s %s\n' % (o, a))
            sys.exit(1)

    if len(args) != 1:
        sys.stderr.write(u'should specific 1 and only 1 service name\n')
        for a in args:
            sys.stderr.write(a)
            sys.stderr.write(u'\n')
        deploy_usage()
        sys.exit(1)
    service_name = args[0]

    if not stack_name:
        sys.stderr.write(u'no stack name')
        deploy_usage()
        sys.exit(1)

    if not conf_dir:
        if u'HOME' in os.environ:
            conf_dir = os.environ['HOME']
        else:
            conf_dir = os.getcwd()
    conf_dir = conf_dir + u'/.clin'

    template, template_dir = load_template(service_name)

    if u'Version' in template:
        v = template[u'Version']
        if v == 1:
            DeployVersion1(template, template_dir, stack_name, productor, region, parameter_file, \
                               use_default, debug, dump_parameter, conf_dir)
        else:
            sys.stderr.write(u'unsupport version: %s' % v)
            sys.exit(1)
    else:
        sys.stderr.write(u'should specific Version in template')
        sys.exit(1)

@subcmd(u'describe')
def clin_describe(argv):
    print(argv)

@subcmd(u'erase')
def clin_erase(argv):

    def erase_usage():
        print(u'erase_usage')

    long_params = [u'stack-name=', u'productor=', u'region=', u'conf-dir']
    try:
        opts, args = getopt.gnu_getopt(argv, u'', long_params)
    except getopt.GetoptError, e:
        erase_usage()
        sys.exit(1)

    stack_name = None
    productor = None
    region = None
    conf_dir = None
    for o, a in opts:
        if o == u'--stack-name':
            stack_name = a
        elif o == u'--productor':
            productor = a
        elif o == u'--region':
            region = a
        elif o == u'--conf-dir':
            conf_dir = a
        else:
            sys.stderr.write(u'invalid args: %s %s\n' % (o, a))
            sys.exit(1)

    if not stack_name:
        sys.stderr.write(u'no stack name')
        erase_usage()
        sys.exit(1)

    if not conf_dir:
        if u'HOME' in os.environ:
            conf_dir = os.environ['HOME']
        else:
            conf_dir = os.getcwd()
    conf_dir = conf_dir + u'/.clin'

    EraseVersion1(stack_name, productor, region, conf_dir)

@subcmd(u'update')
def clin_update(argv):
    print(argv)

def usage():
    print(u'usage')

def main():
    try:
        if sys.argv[1] == u'--help':
            usage()
            sys.exit(0)
        elif sys.argv[1] == u'--version':
            print(u'version')
            sys.exit(0)
        else:
            sub_command = sub_commands[sys.argv[1]]
    except KeyError, e:
        usage()
        sys.exit(1)
    except IndexError, e:
        usage()
        sys.exit(1)

    sub_command(sys.argv[2:])

if __name__ == u'__main__':
    main()
