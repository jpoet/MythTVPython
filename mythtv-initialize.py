#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#---------------------------
# Name: mythtv_source
#---------------------------
__title__ = "mythtv_recording_rules"
__version__= "v0.0.5"

'''
Create a new recording input source

Use: mythtv_source.py --help to get started.

Grab utilties from:
https://github.com/billmeek/MythTVServicesAPI/tree/master/dist

i.e.
`
mkdir -p ~/src/Myth/Python
cd ~/src/Myth/Python
git clone https://github.com/billmeek/MythTVServicesAPI.git
cd MythTVServicesAPI
sudo -H pip3 install dist/mythtv_services_api-0.1.8-py3-none-any.whl
`
'''

import os
import platform
import argparse
from argparse import RawDescriptionHelpFormatter
import json
import logging
import sys
import re
import socket
import traceback

try:
    from MythTV.services_api import send as api
    from MythTV.services_api import utilities as util
except ImportError:
    print('See: https://github.com/billmeek/MythTVServicesAPI\n')
    sys.exit(-1)


TVFORMATS = (
    'NTSC',
    'NTSC-JP',
    'PAL',
    'PAL-60',
    'PAL-BG',
    'PAL-DK',
    'PAL-D',
    'PAL-I',
    'PAL-M',
    'PAL-N',
    'PAL-NC',
    'SECAM',
    'SECAM-D',
    'SECAM-DK',
)

STORAGESCHEDULER = (
    'BalancedFreeSpace',
    'BalancedPercFreeSpace',
    'BalancedDiskIO',
    'Combination',
)

QUEUECPU = (
    "0=Low",
    "1=Medium",
    "2=High",
)

SETTINGS = []

KEYSTRSIZE = 0

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

def process_command_line():
    global SETTINGS

    '''All command line processing is done here.'''
    appname = os.path.basename(sys.argv[0])

    examples = ''

    hostname = socket.getfqdn();
    hostip = socket.gethostbyname(hostname) 

    parser = argparse.ArgumentParser(description='Initial mythbackend setup',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     epilog='Default values are in ().\n'
                                     'Use "{0} save --help" or\n'
                                     '    "{0} storage --help" or\n'
                                     'to see associated options.\n'
                                     '{1}'
                                     .format(appname, examples))

    parser.add_argument('--debug', action='store_true',
                        help='turn on debug messages (%(default)s)')

    parser.add_argument('--digest', type=str, metavar='<user:pass>',
                        help='digest username:password (%(default)s)')

    parser.add_argument('--host', type=str, required=False,
                        default=hostname,
                        metavar='<hostname>', help='Host to modify. (%(default)s)')

    parser.add_argument('--port', type=int, default=6544, metavar='<port>',
                        help='port number of the Services API. (%(default)s)')

    parser.add_argument('--quiet', action='store_true',
                        help='suppress progress messages. (%(default)s)')

    parser.add_argument('--version', action='version', version='%(prog)s 0.11')

    parser.add_argument('--wrmi', action='store_true',
                        help='allow data to be changed. (%(default)s)')

    subparsers = parser.add_subparsers(dest='group', help='')
    
    parser_save = subparsers.add_parser(name='save',
                                        formatter_class=RawDescriptionHelpFormatter,
                                        description='Save settings:',
                                        epilog='{}'.format(examples),
                                        help='Save settings')

    parser.add_argument('--master', action='store_true',
                        help='Initialize a "master" backend (%(default)s)')

    parser.add_argument('--slave', action='store_true',
                        help='Initialize a "slave" backend (%(default)s)')

    parser_save.add_argument('--MasterServerName', type=str, required=False,
                             default=platform.uname()[1], metavar='<name>',
                             help='Master backend hostname (%(default)s)')
    SETTINGS.append('MasterServerName')
   
    parser_save.add_argument('--MasterServerIP', type=str, required=False,
                             default=hostip, metavar='<IP>',
                             help='Master Server Address. (%(default)s)')
    SETTINGS.append('MasterServerIP')

    parser_save.add_argument('--BackendServerIP', type=str, required=False,
                             default=hostip, metavar='<IP>',
                             help='Master Server Address. (%(default)s)')
    SETTINGS.append('BackendServerIP')

    parser_save.add_argument('--BackendServerAddr', type=str, required=False,
                             default=hostip, metavar='<IP>',
                             help='Backend Server Address. (%(default)s)')
    SETTINGS.append('BackendServerAddr')
    
    parser_save.add_argument('--AllowConnFromAll', type=str2bool, required=False,
                             metavar='<bool>',
                             help='Allow connection from other subnets. (%(default)s)')
    SETTINGS.append('AllowConnFromAll')
    
    values = ', '.join(TVFORMATS)
    parser_save.add_argument('--TVFormat', type=str, required=False,
                             metavar='<format>',
                             help=('TV Formats <str> [{}]. (%(default)s)'
                                   .format(values)))
    SETTINGS.append('TVFormat')
    
    parser_save.add_argument('--MythFillEnabled', type=str2bool, required=False,
                             metavar='<bool>',
                             help=('Automatically run mythfilldatabase. '
                                   '(%(default)s)'))
    SETTINGS.append('MythFillEnabled')
    
    parser_save.add_argument('--AutoCommflagWhileRecording', type=str2bool,
                             required=False, metavar='<bool>',
                             help=('Start commercial flagging when recording '
                                   'starts. (%(default)s)'))
    SETTINGS.append('AutoCommflagWhileRecording')
    
    parser_save.add_argument('--JobAllowMetadata', type=str2bool, required=False,
                             metavar='<bool>',
                             help=('Automatically retrieve metadata for recording. '
                                   '(%(default)s)'))
    SETTINGS.append('JobAllowMetadata')
    
    parser_save.add_argument('--JobAllowCommFlag', type=str2bool, required=False,
                             metavar='<bool>',
                             help=('Automatically flag commericals. '
                                   '(%(default)s)'))
    SETTINGS.append('JobAllowCommFlag')
    
    parser_save.add_argument('--JobAllowTranscode', type=str2bool,
                             required=False, metavar='<bool>',
                             help=('Automatically transcode recordings. '
                                   '(%(default)s)'))
    SETTINGS.append('JobAllowTranscode')
    
    parser_save.add_argument('--JobAllowPreview', type=str2bool, required=False,
                             metavar='<bool>',
                             help=('Create preview thumbnails for recordings. '
                                   '(%(default)s)'))
    SETTINGS.append('JobAllowPreview')
    
    values = ', '.join(STORAGESCHEDULER)
    parser_save.add_argument('--StorageScheduler', type=str, required=False,
                             default='Combination',
                             metavar='<scheduler>',
                             help=('Storage Scheduler <str> [{}]. (%(default)s)'
                                   .format(values)))
    SETTINGS.append('StorageScheduler')
    
    parser_save.add_argument('--FreqTable', type=str, required=False,
                             metavar='<table>',
                             help='Default frequency table. (%(default)s)')
    SETTINGS.append('FreqTable')
    
    parser_save.add_argument('--HDRingbufferSize', type=int, required=False,
                             metavar='<bytes>',
                             help='Device ringbuffer size. (%(default)s)')
    SETTINGS.append('HDRingbufferSize')
    
    parser_save.add_argument('--DisableAutomaticBackup', type=str2bool,
                             required=False, default=False, metavar='<bool>',
                             help='backend hostname. (%(default)s)')
    SETTINGS.append('DisableAutomaticBackup')
    
    parser_save.add_argument('--JobQueueMaxSimultaneousJobs', type=int,
                             required=False, default=1, metavar='<int>',
                             help=('Maximum number of jobs allowed to '
                                   'run simultaneously. (%(default)s)'))
    SETTINGS.append('JobQueueMaxSimultaneousJobs')
    
    parser_save.add_argument('--JobQueueCheckFrequency', type=int,
                             required=False, default=60, metavar='<seconds>',
                             help=('How often to check if a job is ready to '
                                   'start. (%(default)s)'))
    SETTINGS.append('JobQueueCheckFrequency')
    
    values = ', '.join(QUEUECPU)
    parser_save.add_argument('--JobQueueCPU', type=int, required=False,
                             default=0, metavar='<int>',
                             help=('JobQueueCPU <int> [{}] (%(default)s).'
                                   .format(values)))
    SETTINGS.append('JobQueueCPU')
    
    parser_storage = subparsers.add_parser(name='storage',
                                           formatter_class=RawDescriptionHelpFormatter,
                                           description='Storage Group settings:',
                                           epilog='{}'.format(examples),
                                           help='Storage group settings')

    parser_storage.add_argument('--name', type=str, required=False,
                                default='Default', metavar='<name>',
                                help='Group name. (%(default)s).')
    
    parser_storage.add_argument('--dir', type=str, required=True,
                                metavar='<path>',
                                help='Storage group directory path. (%(default)s).')

    return vars(parser.parse_args())


def setup(backend, args, opts):
    '''
    Make sure the backend is up (GetHostName) and then set the backend's UTC
    offset for other methods to use.
    '''

    try:
        backend.send(endpoint='Myth/GetHostName', opts=opts)
        int(util.get_utc_offset(backend=backend, opts=opts))
    except ValueError:
        vprint('\nAbort: non integer response from get_utc_offset.', args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort on fatal API error: "{}"'.format(error), args)
        vprint("\nIs mythbackend running?", args);
        sys.exit(-1)

        
def add_storagegroup(backend, args, opts):
    '''
    See: https://www.mythtv.org/wiki/Myth_Service
    '''
    endpoint = 'Myth/AddStorageGroupDir'

    group = {}
    group['HostName']  = args['host']
    group['GroupName'] = args['name']
    group['DirName']   = args['dir']

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=group, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to add storage group: {}. Warning was: {}.'
               .format(group['GroupName'], error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if bool(resp_dict['bool']):
                vprint('Added {0}: "{1}"'.format(group['GroupName'], group['DirName']), args)
            else:
                vprint('Failed to add {0}: "{1}"'.format(group['GroupName'], group['DirName']), args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
        return False

    return True

    

def save_setting(backend, args, opts, key, value):
    '''
    See: https://www.mythtv.org/wiki/Myth_Service
    '''

    endpoint = 'Myth/PutSetting'

    setting = {}
    if not key.startswith('Master'):
        setting['HostName'] = args['MasterServerName']
    setting['Key']      = key
    setting['Value']    = value

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=setting, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to add setting: {}. Warning was: {}.'
               .format(key, error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if bool(resp_dict['bool']):
                vprint('Set {0:{w}} = "{1}"'.format(key, value, w=KEYSTRSIZE), args)
            else:
                vprint('Backend failed to add: "{}"'.format(key), args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
        return False

    return True


def initialize_mythtv(backend, args, opts):
    global KEYSTRSIZE

    for key in SETTINGS:
        KEYSTRSIZE = max(KEYSTRSIZE, len(key))

    for key in SETTINGS:
        if args[key] != None:
            if not save_setting(backend, args, opts, key, args[key]):
                return False

    return True


def vprint(message, args):
    '''
    Verbose Print: print recording rule information unless --quiet
    was used. Not fully implemented, as there are still lots of
    print()s here.

    The intention is that if run out of some other program, this
    will can remain quiet. sys.exit()s will return 1 for failures.
    This may get expanded to put messages in a log...
    '''

    if not args['quiet']:
        print(message)


def main():
    '''
    The primary job of main is to get the arguments from the command line,
    setup logging (and possibly) handle the digest user/password then:

        • Create an instance of the Send class
    '''

    try:
        args = process_command_line()
    except Exception as e:
        print("type error: " + str(e))
        print(traceback.format_exc())
        sys.exit(-1)

    opts = dict()

    logging.basicConfig(level=logging.DEBUG if args['debug'] else logging.INFO)
    logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

    try:
        opts['user'], opts['pass'] = args['digest'].split(':', 1)
    except (AttributeError, ValueError):
        pass

    backend = api.Send(host=args['host'], port=args['port'])

    setup(backend, args, opts)

    if args['group'] == 'save':
        return initialize_mythtv(backend, args, opts)
    if args['group'] == 'storage':
        return add_storagegroup(backend, args, opts)
    else:
        print('An operation must be specified')
        return False

if __name__ == '__main__':
    if not main():
        sys.exit(-1)
    else:
        sys.exit(0)

# vim: set expandtab tabstop=4 shiftwidth=4 smartindent noai colorcolumn=80:
