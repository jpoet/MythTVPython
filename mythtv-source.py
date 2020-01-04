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


CARDTYPES = (
    "QPSK",
    "QAM",
    "OFDM",
    "ATSC",
    "V4L",
    "MPEG",
    "FIREWIRE",
    "HDHOMERUN",
    "FREEBOX",
    "HDPVR",
    "DVB_S2",
    "IMPORT",
    "DEMO",
    "ASI",
    "CETON",
    "EXTERNAL",
    "VBOX",
    "DVB_T2",
    "V4L2ENC",
)

ANALOG_TYPES = (
    "V4L",
    "MPEG",
    "HDPVR",
    "V4L2ENC",
)

INPUTTYPES = (
    'Component',
    'MPEG2TS',
    'DVBInput',
    'Television',
    'Etc.',
)

FREQUENCYTYPES = (
    'default',
    'us-bcast',
    'us-cable',
    'us-cable-hrc',
    'us-cable-irc',
    'japan-bcast',
    'japan-cable',
    'europe-west',
    'europe-east',
    'italy',
    'newzealand',
    'australia',
    'ireland',
    'france',
    'china-bcast',
    'southafrica',
    'argentina',
    'australia-optus',
    'singapore',
    'malaysia',
    'israel-hot-matav',
)

GRABBERTYPES = (
    'schedulesdirect',
    'XMLTV command',
    'None',
)

def process_command_line():
    '''All command line processing is done here.'''
    appname = os.path.basename(sys.argv[0])

    examples = ''

    parser = argparse.ArgumentParser(description='Input configuration',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     epilog='Default values are in ().\n'
                                     'Use "{0} source --help" or\n'
                                     '    "{0} card --help" or\n'
                                     '    "{0} input --help"\n'
                                     'to see associated options.\n'
                                     '{1}'
                                     .format(appname, examples))

    subparsers = parser.add_subparsers(dest='group', help='')

    mandatory = parser.add_argument_group('required arguments')

    parser.add_argument('--debug', action='store_true',
                        help='turn on debug messages (%(default)s)')

    parser.add_argument('--digest', type=str, metavar='<user:pass>',
                        help='digest username:password (%(default)s)')

    parser.add_argument('--host', type=str, required=False,
                        default=socket.gethostname(),
                        metavar='<hostname>', help='backend hostname')

    parser.add_argument('--port', type=int, default=6544, metavar='<port>',
                        help='port number of the Services API (%(default)s)')

    parser.add_argument('--quiet', action='store_true',
                        help='suppress progress messages (%(default)s)')

    parser.add_argument('--sources', action='store_true',
                        help='List configured video sources (%(default)s)')

    parser.add_argument('--channels', type=int, required=False,
                        metavar="<sourceid>",
                        help='List configured channels for sourceid '
                        '(%(default)s)')

    parser.add_argument('--del-channels', type=int, required=False,
                        metavar="<sourceid>",
                        help='Remove all channels for sourceid '
                        '(%(default)s)')

    parser.add_argument('--inputs', action='store_true', required=False,
                        help='List configured capture inputs (%(default)s)')

    parser.add_argument('--version', action='version', version='%(prog)s 0.11')

    parser.add_argument('--wrmi', action='store_true',
                        help='allow data to be changed (%(default)s)')

    ## Source parameters
    examples = ('\nExample:\n'
                '\t{0} source '
                '--name "Twitch" --grabber "None"\n'
                '\t{0} source '
                '--remove 5'.format(appname)
    )

    parser_source = subparsers.add_parser(name='source',
                                          formatter_class=RawDescriptionHelpFormatter,
                                          description='Video source options',
                                          epilog='{}'.format(examples),
                                          help='Video source help')

    parser_source.add_argument('--name', type=str, required=False,
                               metavar='<source name>',
                               help='Name of this channel guide source. '
                               '(%(default)s)')

    values = ', '.join(FREQUENCYTYPES)
    parser_source.add_argument('--frequency', type=str, required=False,
                               metavar='<frequencytable>', default='default',
                               help='Channel frequency table [{}] '
                               '(%(default)s)'.format(values))

    values = ', '.join(GRABBERTYPES)
    parser_source.add_argument('--grabber', type=str, required=False,
                               metavar='<grabber>',
                               help='Source of guide information, i.e. [{}] '
                               '(%(default)s)'.format(values))

    parser_source.add_argument('--userid', type=str, required=False,
                               metavar='<User Id>', default="",
                               help='User ID needed to access grabber data. '
                               '(%(default)s)')

    parser_source.add_argument('--password', type=str, required=False,
                               metavar='<password>',
                               help='Password needed to access grabber data. '
                               '(%(default)s)')

    parser_source.add_argument('--eit', type=bool, required=False,
                               metavar='<bool>', default=False,
                               help='Use EIT to college guide information. '
                               '(%(default)s)')

    parser_source.add_argument('--remove', type=int, required=False,
                        metavar="<sourceid>",
                        help='Remove source for sourceid '
                        '(%(default)s)')

    ## Card parameters
    examples = ('\nExample:\n'
                '\t{0} --wrmi '
                'card --type EXTERNAL '
                '--device "/usr/bin/mythexternrecorder '
                '--conf /home/myth/etc/twitch.conf"'.format(appname)
    )

    parser_card = subparsers.add_parser(name='card',
                                        formatter_class=RawDescriptionHelpFormatter,
                                        description='Capture Card options',
                                        epilog='{}'.format(examples),
                                        help='Capture Card help')

    values = ', '.join(CARDTYPES)
    parser_card.add_argument('--type', type=str, required=True,
                             choices=(CARDTYPES), metavar='<type>',
                             help='Card <type> [{}] (%(default)s)'
                             .format(values))

    parser_card.add_argument('--device', type=str, required=True, 
                             metavar='<device path>', help='Device path')

    parser_card.add_argument('--eit', action='store_true',
                             help='Enable EIT scan on this input (%(default)s)')

    parser_card.add_argument('--ondemand', type=bool, required=False,
                             metavar='<bool>', default=True,
                             help='Only open the capture device when used '
                             'for recording or EIT. Allow other programs to '
                             'access the device when not actively used. '
                             'Enabling can cause recording issues if multiple '
                             'applications contend for the same device. '
                             '(%(default)s)')

    parser_card.add_argument('--signaltimeout', type=int, required=False,
                             metavar='<signaltimeout>', default=2000,
                             help='Number of milliseconds to wait upon '
                             'tuning a frequency before signal is found. '
                             'If this timer expires, tuning has failed. '
                             '(%(default)s)')

    parser_card.add_argument('--channeltimeout', type=int, required=False,
                             metavar='<channeltimeout>', default=20000,
                             help='Number of milliseconds to wait upon '
                             'finding signal before the desired channel '
                             'is found. If this timer expires, tuning '
                             'has failed.'
                             '(%(default)s)')

    parser_card.add_argument('--dvbtuningdelay', type=int, required=False,
                             metavar='<dvbtuningdelay>', default=0,
                             help='Workaround for quirky capture devices. '
                             'Introduce a delay to the tuning process in '
                             'milliseconds. '
                             '(%(default)s)')

    parser_card.add_argument('--diseqcid', type=int, required=False,
                             metavar='<diseqcid>',
                             help='Cross reference this device with a '
                             'DiSEqC tree found in the diseqc_config table. '
                             '(%(default)s)')

    parser_card.add_argument('--eitscan', type=bool, required=False,
                             metavar='<bool>', default=False,
                             help='Permit this device to scan for EIT '
                             'programming data (digital capture devices only). '
                             '(%(default)s)')

    ## Input parameters
    examples = ('\nExample:\n'
                '\t{0} input --cardid 27 --sourceid 8 '
                '--inputtype MPEG2TS --name "Twitch"'.format(appname)
    )

    parser_input = subparsers.add_parser(name='input',
                                         formatter_class=RawDescriptionHelpFormatter,
                                         description='Input options',
                                         epilog='{}'.format(examples),
                                         help='Card Input help')

    parser_input.add_argument('--cardid', type=int, required=True,
                              metavar='<cardid>',
                              help='Card ID this input is connected to '
                              '(%(default)s)')

    parser_input.add_argument('--sourceid', type=int, required=True,
                              metavar='<sourceid>',
                              help='Source ID (%(default)s)')

    values = ', '.join(INPUTTYPES)
    parser_input.add_argument('--inputtype', type=str, required=True,
                              metavar='<inputname>',
                              default='MPEG2TS',
                              help='Input <type> [{}] (%(default)s)'
                             .format(values))

    parser_input.add_argument('--name', type=str, required=True,
                              metavar='<displayname>',
                              help='Short pretty name of input')

    parser_input.add_argument('--externalchannelcommand',
                              type=str, required=False,
                              metavar='<externalcommand>',
                              help='External command used to change channels.')

    parser_input.add_argument('--tunechan', type=int, required=False,
                              metavar='<tunechan>',
                              help='For coaxial inputs, it may be necessary '
                              'to set the tuned channel to 3 or 4, and rely '
                              'on the external device to perform tuning. '
                              '(%(default)s)')
                              
    parser_input.add_argument('--startchan', type=int, required=False,
                              metavar='<startchan>',
                              help='Tune to this channel the next time '
                              'the backend starts. This value is updated '
                              'when the user uses LiveTV. '
                              '(%(default)s)')
                              
    parser_input.add_argument('--priority', type=int, required=False,
                              metavar='<priority>', default=0,
                              help='Recording priority for this input. '
                              '(%(default)s)')

    parser_input.add_argument('--quicktune', type=int, required=False,
                              metavar='<quicktune>', default=2,
                              help='Use quick tuning (on devices which '
                              'accept it). 0 = never, 1 = Live TV Only, '
                              '2 = Always. '
                              '(%(default)s)')

    return vars(parser.parse_args())


def setup(backend, opts, args):
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

def get_sources(backend, args):
    '''
    See: https://www.mythtv.org/wiki/Channel_Service#GetVideoSourceList
    '''
    endpoint = 'Channel/GetVideoSourceList'

    try:
        resp_dict = backend.send(endpoint=endpoint)
    except RuntimeError as error:
        vprint('\nFatal error: "{}"'.format(error), args)
        sys.exit(-1)

    if args['debug']:
        print(json.dumps(resp_dict['VideoSourceList'], sort_keys=True, indent=4,
                         separators=(',', ': ')))

    return resp_dict['VideoSourceList']['VideoSources']


def print_sources(backend, args):
    for source in get_sources(backend, args):
        print('{}: {}'.format(source['Id'], source['SourceName']))

def get_channels(backend, sourceid=None):
    ''' 
    See: https://www.mythtv.org/wiki/Channel_Service#GetChannelInfoList
    '''
    
    endpoint = 'Channel/GetChannelInfoList'
    if sourceid:
        rest = 'SourceID={}&OnlyVisible=false&Details=true'.format(sourceid)
    else:
        rest = 'OnlyVisible=false&Details=true'

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest)
    except RuntimeError as error:
        vprint('\nFatal error: "{}"'.format(error), args)
        sys.exit(-1)
    
    return resp_dict['ChannelInfoList']['ChannelInfos']


def channel2str(channel):
    errata = ''
    if not bool(channel['Visible']):
        errata=" --> Not visible"
    else:
        errata = ''
    return '{0:>6}: {1:>5} {2:15} {3}{4}'.format(channel['ChanId'],
                                                  channel['ChanNum'],
                                                  channel['CallSign'],
                                                  channel['ChannelName'],
                                                  errata)


def print_channels(backend, args, opts):
    for channel in get_channels(backend, sourceid=args['channels']):
        print('{}'.format(channel2str(channel)))


def del_channel(backend, args, opts, channel):
    '''
    See: https://www.mythtv.org/wiki/Channel_Service#RemoveDBChannel
    '''

    endpoint = 'Channel/RemoveDBChannel'

    id = {}
    id['ChannelID'] = channel['ChanId']

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=id, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to remove Channel: [{}]. Error was: {}.'
               .format(channel2str(channel), error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if bool(resp_dict['bool']):
                vprint('Removed Channel [{}]'
                       .format(channel2str(channel)), args)
            else:
                vprint('Backend failed to remove: [{}]'
                       .format(channel2str(channel)), args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
        vprint('Expected a "bool: bool" dictionary response, but got {}'
               .format(resp_dict), args)
        return False

    return True


def del_channels(backend, args, opts, sourceid=None):
    if not sourceid:
        vprint('SourceId is required to delete channels', args)
        sys.exit(-1)

    for channel in get_channels(backend, sourceid):
        if not del_channel(backend, args, opts, channel):
            vprint('Failed to Removed all channels for SourceId {}'
                   .format(sourceid), args)
            return False

    vprint('Removed all channels for SourceId {}'.format(sourceid), args)
    return True


def get_capture_cards(backend, args, opts, hostname=None):
    '''
    See: https://www.mythtv.org/wiki/Capture_Service#GetCaptureCardList
    '''

    endpoint = 'Capture/GetCaptureCardList'
    if hostname:
        rest = 'HostName={}'.format(hostname)
    else:
        rest = ''

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeError as error:
        vprint('\nAbort: Get Capture Card List: Fatal error; "{}"'
               .format(error), args)
        sys.exit(-1)

    if args['debug']:
        print(json.dumps(resp_dict['CaptureCardList'], sort_keys=True, indent=4,
                         separators=(',', ': ')))

    return resp_dict['CaptureCardList']['CaptureCards']

def print_capture_cards(backend, args, opts):
    print('{0:>6}: {1:10} {2:15} {3:10} {4}'
          .format('Id', 'Name', 'CardType', 'Input', 'Host'))
    for inputs in get_capture_cards(backend, args, opts):
        if 'DisplayName' in inputs:
            display = inputs['DisplayName']
        else:
            display = "Not Set"
        if 'InputName' in inputs:
            name = inputs['InputName']
        else:
            name = "Not Set"
        print('{0:>6}: {1:10} {2:15} {3:10} {4}'
              .format(inputs['CardId'], display,
                      inputs['CardType'], name,
                      inputs['HostName']))


def get_capture_card(backend, args, opts):
    '''
    See: https://www.mythtv.org/wiki/Capture_Service#GetCaptureCard
    '''

    if not args['CardId']:
        vprint('\nAbort: get-capture-card requried CardId', args)
        sys.exit(-1)

    endpoint = 'Capture/GetCaptureCard'
    rest = 'CardId={}'.format(args['CardId'])

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeError as error:
        vprint('\nAbort: Get Capture Card: Fatal error; "{}"'
               .format(error), args)
        sys.exit(-1)

    return resp_disc


def add_capture_card(backend, args, opts):
    '''
    See: https://www.mythtv.org/wiki/Capture_Service#AddCaptureCard
    '''

    endpoint = 'Capture/AddCaptureCard'
    card = {}

    # The device path (/dev/video1), device string (12345678-0), IP or
    # URL used to address the device (or playlist for IPTV/HLS).
    card['VideoDevice'] = args['device']
    # The capture card type being created (HDHOMERUN, DEMO, FREEBOX,
    # DVB etc.).
    card['CardType'] = args['type'] # HDHOMERUN, DEMO, FREEBOX, DVB
    if card['CardType'] == 'FIREWIRE':
        card['FirewireModel'] = ''
        card['FirewireSpeed'] = ''
        card['FirewireConnection'] = ''

    if card['CardType'] in ANALOG_TYPES:
        # The device path (/dev/dsp) or device string (ALSA:input) used to
        # address the audio capture device. Usually only useful for
        # framegrabber cards.
        card['AudioDevice'] = ''
        # The device path (/dev/vbi1) used for VBI/CC capture. Usually
        # only useful for a limited number of analog capture devices.
        card['VBIDevice'] = ''
        # The maximum audio sampling rate for captured audio. Usually
        # only useful for framegrabber cards.
        card['AudioRateLimit'] = 0
        card['Contrast'] = 0
        card['Brightness'] = 0
        card['Colour'] = 0
        card['Hue'] = 0

    # The default physical input for the device being created
    # (Component, MPEG2TS, Television, etc.).
    card['DefaultInput'] = 'Television'
    # The backend hostname which houses this new capture device.
    card['HostName'] = args['host']
    # Used only for quirky BT878 DVB cards to prevent the backend
    # adjusting their volume.
    card['SkipBTAudio'] = False
    # Wait for the SEQ start header. Only useful for DVB capture
    # devices.
    card['DVBWaitForSeqStart'] = True
    # Only open the capture device when used for recording or
    # EIT. Allow other programs to access the device when not actively
    # used. Enabling can cause recording issues if multiple
    # applications contend for the same device.
    card['DVBOnDemand'] = args['ondemand']
    # Number of milliseconds to wait upon tuning a frequency before
    # signal is found. If this timer expires, tuning has failed.
    card['SignalTimeout'] = args['signaltimeout']
    # Number of milliseconds to wait upon finding signal before the
    # desired channel is found. If this timer expires, tuning has
    # failed.
    card['ChannelTimeout'] = args['channeltimeout']
    # Workaround for quirky capture devices. Introduce a delay to the
    # tuning process in milliseconds.
    card['DVBTuningDelay'] = args['dvbtuningdelay']
    # Cross reference this device with a DiSEqC tree found in the
    # diseqc_config table.
    if args['diseqcid']:
        card['DiSEqCId'] = args['diseqcid']
    # Permit this device to scan for EIT programming data (digital
    # capture devices only).
    card['DVBEITScan'] = args['eit']

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=card, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to add card: {}. Warning was: {}.'
               .format(card['VideoDevice'], error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    if isinstance(resp_dict, dict) and isinstance(resp_dict['int'], str):

        cardid = int(resp_dict['int'])

        if cardid >= 0:
            vprint('{} added for card "{}".'
                   .format(cardid, card['VideoDevice']), args)
        else:
            cardid = -1
            vprint('Backend failed to add: "{}" (CardId {}).'
                   .format(card['VideoDevice'], cardid), args)
            return False
    else:
        vprint('Expected a "int: int" dictionary response, but got {}'
               .format(resp_dict), args)
        return False

    return True


def video_source_already_exists(backend, args):
    '''
    See if there is already a videosource with this name
    '''
    sources = get_sources(backend, args)
    for source in sources:
        if source['SourceName'] == args['name']:
            if args['debug']:
                print(json.dumps(source, sort_keys=True, indent=4,
                                 separators=(',', ': ')))

            else:
                for source in sources:
                    print('{}: {}'.format(source['Id'], source['SourceName']))

            return True

    return False

    
def add_video_source(backend, args, opts):
    '''
    See https://www.mythtv.org/wiki/Channel_Service#AddVideoSource
    '''

    if video_source_already_exists(backend, args):
        vprint('\nAbort: source {} already exists.'.format(args['name']), args)
        sys.exit(-1)

    endpoint = 'Channel/AddVideoSource'
    source = {}
    
    source['SourceName'] = args['name']
    # source['ConfigPath'] = ''
    source['FreqTable'] = args['frequency']
    #
    if args['grabber'].lower() == 'none':
        source['Grabber'] = '/bin/true'
    elif args['grabber'].lower() == 'schedulesdirect':
        source['Grabber'] = 'schedulesdirect1'
    else:
        source['Grabber'] = args['grabber']
    # source['LineupId'] =
    source['NITId'] = -1
    source['UserId'] = args['userid']
    source['Password'] = args['password']
    source['UseEIT'] = args['eit']

    opts['wrmi'] = args['wrmi']

    print("Grabber '{}'".format(source['Grabber']))

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=source, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to add source: {}. Warning was: {}.'
               .format(source['SourceName'], error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    if isinstance(resp_dict, dict) and isinstance(resp_dict['int'], str):

        sourceid = int(resp_dict['int'])

        if sourceid >= 0:
            vprint('{} added for source "{}".'
                   .format(sourceid, source['SourceName']), args)
        else:
            sourceid = -1
            vprint('Backend failed to add: "{}" (SourceId {}).'
                   .format(source['SourceName'], sourceid), args)
            return False
    else:
        vprint('Expected a "int: int" dictionary response, but got {}'
               .format(resp_dict), args)
        return False

    return True
    
 
def remove_video_source(backend, args, opts):
    '''
    See https://www.mythtv.org/wiki/Channel_Service#RemoveVideoSource
    '''

    source = {}
    for source in get_sources(backend, args):
        if source['Id'] == args['remove']:
            break
        
    if not source:
        print('Source Id {} not found'.format(args['remove']))
        return False

    print('Removing source {}: {}'.format(source['Id'], source['SourceName']))

    endpoint = 'Channel/RemoveVideoSource'

    remove = {}
    remove['SourceID'] = args['remove']

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=remove, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to remove source: {}: {}. Warning was: {}.'
               .format(source['Id'], source['SourceName'], error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if bool(resp_dict['bool']):
                vprint('Removed source {}: {}'
                       .format(source['Id'], source['SourceName']), args)
            else:
                vprint('Backend failed to remove: {}: {}'
                       .format(source['Id'], source['SourceName']), args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
        vprint('Expected a "bool: bool" dictionary response, but got {}'
               .format(resp_dict), args)
        return False

    return True
    
 
def manage_video_source(backend, args, opts):
    if args['remove']:
        return remove_video_source(backend, args, opts)

    return add_video_source(backend, args, opts)


def check_card_input_already_exists(backend, args, opts):
    '''
    See if there is already a card input with this name
    '''
    name_match = False
    id_match   = False
    cards = get_capture_cards(backend, args, opts)
    for card in cards:
        try:
            if card['DisplayName'] == args['name']:
                name_match = True
            else:
                if (int(card['CardId']) == args['cardid'] and card['DisplayName']):
                    id_match = True
        except:
            ...
        if name_match or id_match:
            if args['debug']:
                print(json.dumps(cards, sort_keys=True, indent=4,
                                 separators=(',', ': ')))
            else:
                print_capture_cards(backend, args, opts)

            if name_match:
                vprint('\nAbort: input {} already exists.'
                       .format(args['name']), args)
                sys.exit(-1)
            else:
                vprint('\nAbort: CardID {} already has an input defined.'
                       .format(args['cardid']), args)
                sys.exit(-1)


def add_card_input(backend, args, opts):
    '''
    See https://www.mythtv.org/wiki/Capture_Service#AddCardInput
    '''

    check_card_input_already_exists(backend, args, opts)

    endpoint = 'Capture/AddCardInput'
    input = {}
    
    # The database card number this input belongs to.
    input['CardId'] = args['cardid']
    # The database video source number bound to this card input.
    input['SourceId'] = args['sourceid']
    # The backend hostname where this card input is located.
    input['HostName'] = args['host']
    # The text name of the input (Component, MPEG2TS, Television,
    # etc.)
    input['InputName'] = args['inputtype']
    # The "User Friendly" name for a card input, like "My HD-PVR" or
    # "HDHomeRun Prime 1".
    input['DisplayName'] =  args['name']
    # The path and command for an external channel changing script.
    if args['externalchannelcommand']:
        input['ExternalCommand'] = args['externalchannelcommand']
    # If "Internal" is used as the channel change script, the internal
    # firewire changer will be used, and a ChangerDevice is
    # required. This is the GUID for the attached Firewire set top
    # box.
    input['ChangerDevice'] = 'Internal'
    # If "Internal" is used as the channel change script, the internal
    # firewire changer will be used, and a ChangerModel is required,
    # as defined in firewiredevice.cpp.
    input['ChangerModel'] = 'Internal'
    # For coaxial inputs, it may be necessary to set the tuned channel
    # to 3 or 4, and rely on the external device to perform tuning.
    if args['tunechan']:
        input['TuneChan'] = args['tunechan']
    # Tune to this channel the next time the backend starts. This
    # value is updated when the user uses LiveTV.
    if args['startchan']:
        input['StartChan'] = args['startchan']
    # Enable the use of long-term EIT data if using a DVB-S tuner and
    # Dish Network.
    input['DishnetEIT'] = False
    # A recording priority modification for this card input.
    input['RecPriority'] = args['priority']
    # Use quick tuning (on devices which accept it). 0 = never, 1 =
    # Live TV Only, 2 = Always
    input['Quicktune'] = args['quicktune']
    input['SchedOrder'] = 1

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=input, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to add input: {}. Warning was: {}.'
               .format(input['InputName'], error), args)
        sys.exit(-1)
    except RuntimeError as error:
        vprint('\nAbort: Fatal API Error response: {}\n'.format(error), args)
        sys.exit(-1)

    opts['wrmi'] = False

    if isinstance(resp_dict, dict) and isinstance(resp_dict['int'], str):

        inputid = int(resp_dict['int'])

        if inputid >= 0:
            vprint('{} added for input "{}".'
                   .format(inputid, input['DisplayName']), args)
        else:
            inputid = -1
            vprint('Backend failed to add: "{}" (InputId {}).'
                   .format(input['DisplayName'], inputid), args)
            return False
    else:
        vprint('Expected a "int: int" dictionary response, but got {}'
               .format(resp_dict), args)
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
        • See if a rule exists for --title
        • Get the selected template
        • Get data for command line title from the guide
        • Update the template with the guide data
        • Add the rule on the backend.
    '''

    try:
        args = process_command_line()
    except:
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

    setup(backend, opts, args)

    if args['sources']:
        return print_sources(backend, args)
    elif args['channels']:
        return print_channels(backend, args, opts)
    elif args['del_channels']:
        return del_channels(backend, args, opts, sourceid = args['del_channels'])
    elif args['inputs']:
        return print_capture_cards(backend, args, opts)
    else:
        if args['group'] == 'card':
            return add_capture_card(backend, args, opts)
        elif args['group'] == 'source':
            return manage_video_source(backend, args, opts)
        elif args['group'] == 'input':
            return add_card_input(backend, args, opts)

    vprint("Option not handled", args)
    sys.exit(-1)

if __name__ == '__main__':
    if not main():
        sys.exit(-1)
    else:
        sys.exit(0)

# vim: set expandtab tabstop=4 shiftwidth=4 smartindent noai colorcolumn=80:
