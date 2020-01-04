#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#---------------------------
# Name: mythtv_recording_rules
#---------------------------
__title__   = "mythtv-record"
__version__ = "v0.0.6"

'''
Create a new recording rule for the title passed on the command line.

Use: mythtv_record.py --help to get started.

The --title <title> must match a program name exactly and it will also
become the name of the new recording rule. If the rule already exists,
the program will abort.


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

#from __future__ import print_function
#from __future__ import absolute_import
from datetime import tzinfo, timedelta, datetime, timezone
import argparse
from argparse import RawDescriptionHelpFormatter
import json
import logging
import os
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


WHITE = '\033[0m'
YELLOW = '\033[93m'

WIDTH = {}
WIDTH['id'] = 2
WIDTH['chanid'] = 6
WIDTH['callsign'] = 5
WIDTH['rectype'] = 5
WIDTH['title'] = 5
WIDTH['start'] = 5
WIDTH['end'] = 5
WIDTH['priority'] = 5
WIDTH['inactive'] = 5
WIDTH['profile'] = 5
WIDTH['recgroup'] = 5
WIDTH['playgroup'] = 5
WIDTH['expire'] = 5
WIDTH['input'] = 5
WIDTH['subtitle'] = 8
WIDTH['status'] = 6

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

if sys.version_info >= (3,6,0):
    def LocalTimezone():
        return datetime.now().astimezone().tzinfo
else:
    import time as _time

    ZERO = timedelta(0)
    STDOFFSET = timedelta(seconds = -_time.timezone)
    if _time.daylight:
        DSTOFFSET = timedelta(seconds = -_time.altzone)
    else:
        DSTOFFSET = STDOFFSET
        
    DSTDIFF = DSTOFFSET - STDOFFSET
        
    class LocalTimezone(tzinfo):
            
        def utcoffset(self, dt):
            if self._isdst(dt):
                return DSTOFFSET
            else:
                return STDOFFSET
            
        def dst(self, dt):
            if self._isdst(dt):
                return DSTDIFF
            else:
                return ZERO

        def tzname(self, dt):
            return _time.tzname[self._isdst(dt)]

        def _isdst(self, dt):
            tt = (dt.year, dt.month, dt.day,
                  dt.hour, dt.minute, dt.second,
                  dt.weekday(), 0, 0)
            stamp = _time.mktime(tt)
            tt = _time.localtime(stamp)
            return tt.tm_isdst > 0

localtz = LocalTimezone()
utcnow  = datetime.utcnow().replace(tzinfo=timezone.utc)
        
def datefromisostr(datestr):
    regex = r'^(?P<year>[0-9]{4})(?P<hyphen>-?)(?P<month>1[0-2]|0[1-9])(?P=hyphen)(?P<day>3[01]|0[1-9]|[12][0-9])T(?P<hour>2[0-3]|[01][0-9]):?(?P<minute>[0-5][0-9]):?(?P<second>[0-5][0-9])(?P<timezone>Z|[+-](?:2[0-3]|[01][0-9])(?::?(?:[0-5][0-9]))?)?$'

    match_iso8601 = re.compile(regex)
    m = match_iso8601.search(datestr)

    dt = datetime(year  =  int(m.group('year')),
                  month =  int(m.group('month')),
                  day   =  int(m.group('day')),
                  hour   = int(m.group('hour')),
                  minute = int(m.group('minute')),
                  second = int(m.group('second'))
    )

    if m.group('timezone'):
        if m.group('timezone') == 'Z':
            tz = timezone.utc
        else:
            zone = m.group('timezone').replace(':', '')
            struct_time = datetime.strptime(zone, "%z")
            tz = struct_time.tzinfo
    else:
        tz = localtz

    dt = dt.replace(tzinfo=tz)
    return dt



WEEKDAYAFTER = (lambda date, day: date + 
                timedelta(days = (day - date.weekday() + 7) % 7))

TYPES = (
    "All",
    "Daily",
    "One",
    "Single",
    "Weekly",
)

def record_type(key):
    switch = {
        'All'    : 'Record All',
        'Daily'  : 'Record Daily',
        'One'    : 'Record One',
        'Single' : 'Single Record',
        'Weekly' : 'Record Weekly'
    }
    return switch.get(key, None)


def process_command_line():
    '''All command line processing is done here.'''

    appname = os.path.basename(sys.argv[0])

    examples = ('\nExamples:\n'
                '\tList current recording rules:\n'
                '\t\t{0} --rules\n'
                '\tList current sources:\n'
                '\t\t{0} --sources\n'
                '\tList channels for a source:\n'
                '\t\t{0} --channels <sourceid>\n'
                .format(appname)
    )

    parser = argparse.ArgumentParser(description='Add a recording rule',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     epilog='Default values are in ().\n'
                                     'Use "{0} add --help" or\n'
                                     '    "{0} remove --help or"\n'
                                     '    "{0} upcoming --help"\n'
                                     '    "{0} stop --help"\n'
                                     '    "{0} reactivate --help"\n'
                                     'to see associated options.\n\n{1}'
                                     .format(appname, examples))

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
                        help=('List configured channels for sourceid '
                              '(%(default)s)'))

    parser.add_argument('--rules', action='store_true',
                        help='List recording rules. (%(default)s)')

    parser.add_argument('--templates', action='store_true',
                        help='List configured templates (%(default)s)')

    parser.add_argument('--version', action='version', version='%(prog)s 0.11')

    parser.add_argument('--wrmi', action='store_true',
                        help='allow data to be changed (%(default)s)')

    subparsers = parser.add_subparsers(dest='group', help='')

    examples = ('\nExamples:\n'
                '\tManual record 24x7 on chanid 80017:\n'
                '\t\t{0} add --manual --type All --chanid 80017 --title '
                '"Manual Record 80017"\n'
                '\tManual record 24x7 on sourceid 2 and channel number 5:\n'
                '\t\t{0} add --manual --type All --sourceid 2 --channum 5 --title '
                '"Manual Record 80017"\n'
                '\tManual record single:\n'
                '\t\t{0} add --manual --type Single --chanid 80017 '
                '--starttime 2018-08-05T17:00:00 --duration 60 '
                '--title "Manual Record One"\n'
                '\tRecord all for title:\n'
                '\t\t{0} add --type All --title "NCIS"\n'
                .format(appname)
    )

    parser_add = subparsers.add_parser(name='add',
                                       formatter_class=RawDescriptionHelpFormatter,
                                       description='Add schedule:',
                                       epilog='{}'.format(examples),
                                       help='Add schedule')

    parser_add.add_argument('--template', type=str, required=False,
                            default='Default', metavar='<temp>',
                            help='template name, (%(default)s)')

    parser_add.add_argument('--title', type=str, required=False,
                            metavar='<title>',
                            help='full program name')

    parser_add.add_argument('--subtitle', type=str, required=False,
                            metavar='<subtitle>',
                            help='program subtitle')

    parser_add.add_argument('--description', type=str, required=False,
                            metavar='<description>',
                            help='program description')

    parser_add.add_argument('--chanid', type=str, required=False,
                            metavar="<chanid>",
                            help='Record on this channel Id')

    parser_add.add_argument('--sourceid', type=str, required=False,
                            metavar="<sourceid>",
                            help='Record channel on this sourceid')

    parser_add.add_argument('--channum', type=str, required=False,
                            metavar="<chan number>",
                            help='Record on this channel')

    parser_add.add_argument('--manual', action='store_true',
                            help='Create manual record rule (%(default)s)')

    parser_add.add_argument('--starttime', type=str, required=False,
                            metavar="<datetime>",
                            help='Manual record start datetime '
                            'in ISO format. i.e. "2018-08-05T05:00:00" '
                            '(%(default)s))')

    parser_add.add_argument('--duration', type=int, required=False,
                            metavar="<duration>", default = 60,
                            help='Manual record duration in minutes '
                            '(%(default)s)')

    parser_add.add_argument('--season', type=int, required=False,
                            metavar="<season>", default = 0,
                            help='Season number'
                            '(%(default)s)')

    parser_add.add_argument('--episode', type=int, required=False,
                            metavar="<episode>", default = 0,
                            help='Episode number '
                            '(%(default)s)')

    values = ', '.join(TYPES)
    parser_add.add_argument('--type', type=str, required=True, choices=(TYPES),
                            metavar='<type>',
                            help='Record <type> [{}] (%(default)s)'
                            .format(values))

    examples = ('\nExamples:\n'
                '\tRemove Manual record 24x7 on chanid 80017:\n'
                '\t\t{0} remove --manual --type All --chanid 80017\n'
                '\tRemove Manual record 24x7 on sourceid 3 and channel number 4:\n'
                '\t\t{0} remove --manual --type All --sourceid 3 --channum 4\n'
                '\tRemove Manual record @ 5pm (local time):\n'
                '\t\t{0} remove --manual --type Single --chanid 80017 '
                '--starttime 2018-08-05T17:00:00\n'
                '\tRemove Manual record @ 5pm (UTC):\n'
                '\t\t{0} remove --manual --type Single --chanid 80017 '
                '--starttime 2018-08-05T17:00:00Z\n'
                '\tRemove recording rule with Id 3421:\n'
                '\t\t{0} remove --recordid 3421\n'
                '\tRemove recording rule for title "NCIS":\n'
                '\t\t{0} remove --title "NCIS"\n'
                .format(appname)
                )

    parser_del = subparsers.add_parser(name='remove',
                                       formatter_class=RawDescriptionHelpFormatter,
                                       description='Remove schedule:',
                                       epilog='{}'.format(examples),
                                       help='Remove schedule')

    parser_del.add_argument('--title', type=str, required=False,
                            metavar='<title>',
                            help='full program name, no wild cards/regex')

    parser_del.add_argument('--recordid', type=str, required=False,
                            metavar="<recordid>",
                            help='Rule Id')

    parser_del.add_argument('--chanid', type=str, required=False,
                            metavar="<chanid>",
                            help='Channel Id')

    parser_del.add_argument('--sourceid', type=str, required=False,
                            metavar="<sourceid>",
                            help='Record channel on this sourceid')

    parser_del.add_argument('--channum', type=str, required=False,
                            metavar="<chan number>",
                            help='Record on this channel number')

    parser_del.add_argument('--manual', action='store_true',
                            help='Create manual record rule (%(default)s)')

    parser_del.add_argument('--starttime', type=str, required=False,
                            metavar="<datetime>",
                            help='Manual record start datetime '
                            'in ISO format. i.e. "2018-08-05T05:00:00" '
                            '(%(default)s))')

    values = ', '.join(TYPES)
    parser_del.add_argument('--type', type=str, required=False, choices=(TYPES),
                            metavar='<type>',
                            help='Record <type> [{}] (%(default)s)'.format(values))

    examples = ('\nExamples:\n'
                '\tShow the next 7 days of schedule recordings:\n'
                '\t\t{0} upcoming\n'
                '\tShow the next 7 days of potential recordings:\n'
                '\t\t{0} upcoming --all\n'
                '\tShow only current recordings:\n'
                '\t\t{0} upcoming --current\n'
                .format(appname)
                )

    parser_upcoming = subparsers.add_parser(name='upcoming',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     description='List scheduled recordings:',
                                     epilog='{}'.format(examples),
                                     help='Show schedule')


    parser_upcoming.add_argument('--chanid', type=int, required=False,
                                 metavar='<chanid>',
                                 help='filter on MythTV chanid, e.g. 1091. '
                                 '(%(default)s))')

    parser_upcoming.add_argument('--days', type=int, required=False,
                                 metavar='<days>', default=7,
                                 help='days of programs to print (%(default)s)')

    parser_upcoming.add_argument('--all', action='store_true',
                                 help='include conflicts etc. (%(default)s)')

    parser_upcoming.add_argument('--current', action='store_true',
                                 help=('Show only currently recording. '
                                       '(%(default)s)'))

    parser_upcoming.add_argument('--title', type=str, default='', required=False,
                                 metavar='<title>',
                                 help='filter by title (%(default)s))')


    examples = ''
    parser_stop = subparsers.add_parser(name='stop',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     description='Stop a current recording',
                                     epilog='{}'.format(examples),
                                     help='Stop in progress recording')

    parser_stop.add_argument('--recordid', type=int, required=False,
                                 metavar='<recordid>',
                                 help='Stop recording with id. '
                                 '(%(default)s))')

    parser_stop.add_argument('--chanid', type=str, required=False,
                            metavar="<chanid>",
                            help='Record on this channel Id')

    parser_stop.add_argument('--starttime', type=str, required=False,
                            metavar="<datetime>",
                            help='Manual record start datetime '
                            'in ISO format. i.e. "2018-08-05T05:00:00" '
                            '(%(default)s))')

    parser_stop.add_argument('--title', type=str, required=False,
                                 metavar='<title>',
                                 help=('Stop current recording with title '
                                       '(%(default)s))'))

    examples = ''
    parser_reactivate = subparsers.add_parser(name='reactivate',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     description=('Reactivate a stopped '
                                                  'recording'),
                                     epilog='{}'.format(examples),
                                     help='Reactivate a stopped recording')

    parser_reactivate.add_argument('--recordid', type=int, required=False,
                                 metavar='<recordid>',
                                 help='Reactivate recording with id. '
                                 '(%(default)s))')

    parser_reactivate.add_argument('--chanid', type=str, required=False,
                                   metavar="<chanid>",
                                   help='Record on this channel Id')

    parser_reactivate.add_argument('--starttime', type=str, required=False,
                                   metavar="<datetime>",
                                   help='Manual record start datetime '
                                   'in ISO format. i.e. "2018-08-05T05:00:00" '
                                   '(%(default)s))')

    parser_reactivate.add_argument('--title', type=str, required=False,
                                 metavar='<title>',
                                 help=('Reactivate current recording with title '
                                       '(%(default)s))'))

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
        sys.exit('\nFatal error: "{}"'.format(error))

    if args['debug']:
        print(json.dumps(resp_dict['VideoSoruceList'], sort_keys=True, indent=4,
                         separators=(',', ': ')))

    return resp_dict['VideoSourceList']['VideoSources']


def print_sources(backend, args):
    for source in get_sources(backend, args):
        print('{}: {}'.format(source['Id'], source['SourceName']))


def get_template(backend, args, opts):
    '''
    Gets the requested (or default) template. This will be modified
    with guide data for the title of interest, then send to the
    backend in a POST. Misspelled template names return the Default
    template.

    Only the template name is used, not the trailing: (Template) text.
    '''

    endpoint = 'Dvr/GetRecordSchedule'
    rest = 'Template={}'.format(args['template'])

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeError as error:
        sys.exit('\nAbort, Get Template: Fatal error; "{}"'.format(error))

    if args['debug']:
        print(json.dumps(resp_dict['RecRule'], sort_keys=True, indent=4,
                         separators=(',', ': ')))

    # Templates are always Id -1, just double checking here...
    if resp_dict['RecRule']['Id'] != '-1':
        return None

    return resp_dict['RecRule']


def get_templates(backend, args):
    '''
    Find all the templates from the list of schedules.
    '''

    templates = []
    for rule in get_recording_rules(backend, args):
        if rule['Type'] == 'Recording Template':
            templates.append(rule)

    return templates


def recording_template_str(rule):
    result = ('{id:{id_width}}: '
              '{rectype:{rectype_width}} '
              '{title:{title_width}} '
              'Priority:{priority:{priority_width}}  '
              'Profile:{profile:{profile_width}} '
              'RecGroup:{recgroup:{recgroup_width}} '
              'PlayGroup:{playgroup:{playgroup_width}} '
              'Expire:{expire:{expire_width}}'
              .format(id = rule['Id'],
                      id_width = WIDTH['id'],
                      rectype = rule['Type'],
                      rectype_width = WIDTH['rectype'],
                      title = rule['Title'],
                      title_width = WIDTH['title'],
                      priority = rule['RecPriority'],
                      priority_width = WIDTH['priority'],
                      profile = rule['RecProfile'],
                      profile_width = WIDTH['profile'],
                      recgroup = rule['RecGroup'],
                      recgroup_width = WIDTH['recgroup'],
                      playgroup = rule['PlayGroup'],
                      playgroup_width = WIDTH['playgroup'],
                      expire = rule['AutoExpire'],
                      expire_width = WIDTH['expire']
              )
    )
    return result


def print_templates(backend, args):
    global WIDTH
    
    for rule in get_templates(backend, args):
        WIDTH['id'] = max(WIDTH['id'], len(rule['Id']))
        WIDTH['rectype'] = max(WIDTH['rectype'], len(rule['Type']))
        WIDTH['title'] = max(WIDTH['title'], len(rule['Title']))
        WIDTH['priority'] = max(WIDTH['priority'], len(rule['RecPriority']))
        WIDTH['profile'] = max(WIDTH['profile'], len(rule['RecProfile']))
        WIDTH['recgroup'] = max(WIDTH['recgroup'], len(rule['RecGroup']))
        WIDTH['playgroup'] = max(WIDTH['playgroup'], len(rule['PlayGroup']))
        WIDTH['expire'] = max(WIDTH['expire'], len(rule['AutoExpire']))

    for rule in get_templates(backend, args):
        print('{}'.format(recording_template_str(rule)))


def get_program_data(backend, args, opts):
    '''
    Find matching program(s) from the guide. Note that if --title=Blah,
    then any title with the string Blah in it will be returned by
    GetProgramList.
    '''

    endpoint = 'Guide/GetProgramList'
    rest = 'Details=False&WithInvisible=True&TitleFilter={}'.format(
        args['title'])

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeError as error:
        sys.exit('\nAbort, Get Upcoming: Fatal error; "{}"'.format(error))

    count = int(resp_dict['ProgramList']['TotalAvailable'])

    if args['debug']:
        print('\nDebug: Programs matching --title {} = {}'
              .format(args['title'], count))

    if count < 1:
        sys.exit('\nAbort, No programs in the guide matching: {}.\n'
                 .format(args['title']))

    for program in resp_dict['ProgramList']['Programs']:
        if args['debug']:
            print('Comparing {} to {}'.format(args['title'], program['Title']))
        if program['Title'] == args['title']:
            if args['debug']:
                print(json.dumps(program, sort_keys=True, indent=4,
                                 separators=(',', ': ')))
            return program

        continue

    return None


def get_recording_ruleid(backend, args, chanid, starttime):
    dt = datefromisostr(starttime)
    # Convert to UTC
    start = dt.astimezone(tz=timezone.utc)
    startstr = "{}".format(start.isoformat().replace('+00:00', 'Z'))
        
    for rule in get_recording_rules(backend, args):
        if (rule['StartTime'] == startstr and rule['ChanId'] == chanid):
            return rule['Id']

    vprint('Failed to find a RecordId for chanid {} starttime {}'
           .format(args['chanid'], startstr), args)
    return None
    

def get_recording_rule(backend, args, recordid):
    '''
    See: https://www.mythtv.org/wiki/DVR_Service#GetRecordSchedule
    '''

    endpoint = 'Dvr/GetRecordSchedule'
    rest = 'RecordId={}'.format(recordid)

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest)
    except RuntimeError as error:
        vprint('\nFatal error: "{}"'.format(error), args)
        sys.exit(-1)

    return resp_dict['RecRule']


def get_recording_rules(backend, args):
    '''
    See: https://www.mythtv.org/wiki/DVR_Service#GetRecordScheduleList
    '''

    endpoint = 'Dvr/GetRecordScheduleList'
    rest = 'StartIndex=0'

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest)
    except RuntimeError as error:
        vprintrf('\nFatal error: "{}"'.format(error), args)
        sys.exit(-1)
    
    try:
        return resp_dict['RecRuleList']['RecRules']
    except:
        print(traceback.format_exc())
        return None


def schedule_already_exists(backend, args, opts):
    '''
    See if there's already a rule for the title.
    '''

    for rule in get_recording_rules(backend, args):
        if rule['Title'] == args['title']:
            if args['debug']:
                print(json.dumps(rule, sort_keys=True, indent=4,
                                 separators=(',', ': ')))

            return True

    return False


def recording_rule_str(rule):
    if 'id' in rule:
        id = rule['Id']
    else:
        id = -1

    result = ('{id:{id_width}}: {chanid:{chanid_width}} '
              '{callsign:{callsign_width}} {rectype:{rectype_width}} '
              '{title:{title_width}} Start:{start:{start_width}}  '
              'End:{end:{end_width}}  Priority:{priority:{priority_width}}  '
              'Inactive:{inactive:{inactive_width}}  '
              'Profile:{profile:{profile_width}} '
              'RecGroup:{recgroup:{recgroup_width}} '
              'PlayGroup:{playgroup:{playgroup_width}} '
              'Expire:{expire:{expire_width}}'
              .format(id = id,
                      id_width = WIDTH['id'],
                      chanid = rule['ChanId'],
                      chanid_width = WIDTH['chanid'],
                      callsign = rule['CallSign'],
                      callsign_width = WIDTH['callsign'],
                      rectype = rule['Type'],
                      rectype_width = WIDTH['rectype'],
                      title = rule['Title'],
                      title_width = WIDTH['title'],
                      start = rule['StartTime'],
                      start_width = WIDTH['start'],
                      end = rule['EndTime'],
                      end_width = WIDTH['end'],
                      priority = rule['RecPriority'],
                      priority_width = WIDTH['priority'],
                      inactive = rule['Inactive'],
                      inactive_width = WIDTH['inactive'],
                      profile = rule['RecProfile'],
                      profile_width = WIDTH['profile'],
                      recgroup = rule['RecGroup'],
                      recgroup_width = WIDTH['recgroup'],
                      playgroup = rule['PlayGroup'],
                      playgroup_width = WIDTH['playgroup'],
                      expire = rule['AutoExpire'],
                      expire_width = WIDTH['expire']
              )
    )
    return result

def print_recording_rules(backend, args):
    global WIDTH
    
    for rule in get_recording_rules(backend, args):
        WIDTH['id'] = max(WIDTH['id'], len(rule['Id']))
        WIDTH['chanid'] = max(WIDTH['chanid'], len(rule['ChanId']))
        WIDTH['callsign'] = max(WIDTH['callsign'], len(rule['CallSign']))
        WIDTH['rectype'] = max(WIDTH['rectype'], len(rule['Type']))
        WIDTH['title'] = max(WIDTH['title'], len(rule['Title']))
        WIDTH['start'] = max(WIDTH['start'], len(rule['StartTime']))
        WIDTH['end'] = max(WIDTH['end'], len(rule['EndTime']))
        WIDTH['priority'] = max(WIDTH['priority'], len(rule['RecPriority']))
        WIDTH['inactive'] = max(WIDTH['inactive'], len(rule['Inactive']))
        WIDTH['profile'] = max(WIDTH['profile'], len(rule['RecProfile']))
        WIDTH['recgroup'] = max(WIDTH['recgroup'], len(rule['RecGroup']))
        WIDTH['playgroup'] = max(WIDTH['playgroup'], len(rule['PlayGroup']))
        WIDTH['expire'] = max(WIDTH['expire'], len(rule['AutoExpire']))

    for rule in get_recording_rules(backend, args):
        print('{}'.format(recording_rule_str(rule)))

def update_template(template, guide_data, args):
    '''
    Put selected guide information into the template to be sent as
    postdata for the new rule.
    '''

    try:
        template['StartTime'] = guide_data['StartTime']
        template['EndTime']   = guide_data['EndTime']
        template['Title']     = guide_data['Title']
        template['Type']      = record_type(args['type'])
        template['Station']   = guide_data['Channel']['CallSign']
        template['ChanId']    = guide_data['Channel']['ChanId']
        template['SearchType'] = 'None'
        template['Category']  = guide_data['Category']
        template['FindTime']  = util.create_find_time(guide_data['StartTime'])
        template['Description'] = 'Rule created by add_recording_rule.py'
    except KeyError as e:
        print('guide data missing "{}" element.').format(e)
        return False

    return True


def add_record_rule(backend, template, args, opts):
    '''
    Send the changed data to the backend.
    '''

    endpoint = 'Dvr/AddRecordSchedule'

    params_not_sent = ('AverageDelay', 'CallSign', 'Id', 'LastDeleted',
                       'LastRecorded', 'NextRecording', 'ParentId')

    for param in params_not_sent:
        try:
            del template[param]
        except KeyError:
            pass

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=template,
                                 opts=opts)
    except RuntimeWarning as error:
        sys.exit('Abort, Unable to add rule: {}. Warning was: {}.'
                 .format(template['Title'], error))
    except RuntimeError as error:
        vprint('\nAbort, Fatal API Error response: {}\n'.format(error), args)
        print(traceback.format_exc())
        sys.exit(-1)

    opts['wrmi'] = False

    if isinstance(resp_dict, dict) and isinstance(resp_dict['uint'], str):

        recording_rule = int(resp_dict['uint'])

        if recording_rule < 4294967295:
            vprint('\nAdded: "{}" (RecordId {}).'
                   .format(template['Title'], recording_rule), args)
        else:
            recording_rule = -1
            vprint('Backend failed to add: "{}" (RecordId {}).\n{}'
                   .format(template['Title'], recording_rule, resp_dict), args)
            return False
    else:
        vprint('Expected a "uint: int" dictionary response, but got {}'
               .format(resp_dict), args)
        return False

    return True


def record_title(backend, args, opts):
    template = get_template(backend, args, opts)
    if not template:
        sys.exit('\nAbort, no template found for: {}.'.format(args['title']))

    guide_data = get_program_data(backend, args, opts)
    if not guide_data:
        sys.exit('\nAbort, no match in guide for: {}'.format(args['title']))

    if update_template(template, guide_data, args):
        add_record_rule(backend, template, args, opts)
    else:
        print('Guide data: {}'.format(guide_data))
        sys.exit('\nAbort, error while copying guide data to template.')


def get_channels(backend, sourceid):
    ''' 
    See: https://www.mythtv.org/wiki/Channel_Service#GetChannelInfoList
    '''
    
    endpoint = 'Channel/GetChannelInfoList'
    rest = 'SoruceID={}&OnlyVisible=true&Details=true'.format(sourceid)

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest)
    except RuntimeError as error:
        sys.exit('\nFatal error: "{}"'.format(error))
    
    return resp_dict['ChannelInfoList']['ChannelInfos']


def print_channels(backend, args):
    for channels in get_channels(backend, args['channels']):
            print('{0:>6}: {1:>5} {2:10} {3}'.format(channels['ChanId'],
                                                     channels['ChanNum'],
                                                     channels['CallSign'],
                                                     channels['ChannelName']))
    

def get_channel(backend, chanid):
    ''' 
    See: https://www.mythtv.org/wiki/Channel_Service#GetChannelInfo
    '''
    
    endpoint = 'Channel/GetChannelInfo'
    rest = 'ChanID={}&OnlyVisible=true&Details=true'.format(chanid)

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest)
    except RuntimeError as error:
        sys.exit('\nFatal error: "{}"'.format(error))
    
    return resp_dict['ChannelInfo']


def get_chanid(backend, sourceid, channum):
    for chan in get_channels(backend, sourceid):
        if chan['ChanNum'] == channum:
            return chan['ChanId']
    return None


def record_manual_type(backend, args, opts, type, chaninfo,
                       template, starttime, duration):
    if not starttime:
        sys.exit('\nAbort, manul record: no starttime provided.')

    global localtz

    # Convert to UTC
    start = starttime.replace(tzinfo=localtz).astimezone(tz=timezone.utc)
    end   = starttime + timedelta(minutes = duration)
    end   = end.replace(tzinfo=localtz).astimezone(tz=timezone.utc)

    template['StartTime']  = "{}".format(start.isoformat()
                                         .replace('+00:00', 'Z'))
    template['EndTime']    = "{}".format(end.isoformat()
                                         .replace('+00:00', 'Z'))
    template['Description'] = ('{} (Manual Record)'
                              .format(starttime.strftime('%H')))
    template['FindTime']   = starttime.strftime('%H:%M:%S')

    template['Type']       = record_type(type)
    template['Title']      = args['title']
    if args['subtitle']:
        template['SubTitle']   = args['subtitle']
    if args['description']:
        template['Description'] = args['description']
    if args['season']:
        template['Season'] = args['season']
    if args['episode']:
        template['Episode'] = args['episode']
    template['Station']    = chaninfo['CallSign']
    template['CallSign']   = chaninfo['CallSign']

    print('{}'.format(recording_rule_str(template)))

    return add_record_rule(backend, template, args, opts)
    

def record_manual_24x7(backend, args, opts, chaninfo, rec24x7, duration):
    global localtz

    # First Saturday in January, resuling in 7-day/week schedule
    saturday = WEEKDAYAFTER(datetime(2018, 1, 1, tzinfo=localtz), 5)

    blocks_in_day = range(24);
    if duration < 60:
        blocks_in_day = range(int(24 * 60 / duration))
    else:
        blocks_in_day = range(int(24 * duration / 60))
    
    start = saturday
    for block in list(blocks_in_day):
        rec24x7['SubTitle'] = 'hour {}'.format(start.strftime('%H'))

        if not record_manual_type(backend, args, opts, 'Daily',
                                  chaninfo, rec24x7, start, duration):
            return False

        start = start + timedelta(minutes = duration)

    return True
    

def record_manual(backend, args, opts):
    template = get_template(backend, args, opts)
    if not template:
        sys.exit('\nAbort, no template found for: {}.'.format(args['template']))

    if args['chanid']:
        chanid = args['chanid']
    else:
        chanid = get_chanid(backend, args['sourceid'], args['channum'])
        
    if not chanid:
        vprint('\nAbort, no channel provided for manual record.', args)
        sys.exit(-1)

    template['ChanId']     = chanid
    template['SearchType'] = 'Manual Search'
    template['Category']   = ''
    template['SeriesId']   = ''

    chaninfo = get_channel(backend, chanid)
    if not chaninfo:
        vprint('Channel ID {} not found in available channels.'.format(chanid),
               args)
        return False

    if (args['type'] == 'All'):
        record_manual_24x7(backend, args, opts, chaninfo, template,
                           int(args['duration']))
    else:
        if not args['starttime']:
            vprint('starttime required for this type.', args)
            return False
        dt = datefromisostr(args['starttime'])
        record_manual_type(backend, args, opts, args['type'], chaninfo, template,
                           dt, int(args['duration']))
        

def remove_record_rule(backend, args, opts, rule):
    '''
    See https://www.mythtv.org/wiki/DVR_Service#RemoveRecordSchedule
    '''
    if not rule:
        vprint('A valid recording rule must exist before it can be removed.',
                args)
        return False

    endpoint = 'Dvr/RemoveRecordSchedule'

    vprint('Removing recording rule:\n{}'.format(recording_rule_str(rule)), args)
    id = {}
    id['RecordId'] = rule['Id']
    
    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, postdata=id, opts=opts)
    except RuntimeWarning as error:
        vprint('Abort: Unable to remove RecordID {}. Warning was: {}.'
               .format(rule['Id'], error), args)
        return False
    except RuntimeError as error:
        vprint('\nAbort, Fatal API Error response: {}\n'.format(error), args)
        print(traceback.format_exc())
        sys.exit(-1)

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if not str2bool(resp_dict['bool']):
                vprint('Backend failed to remove Id: "{}"'.format(rule['Id']),
                       args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
        return False

    return True


def remove_record_ruleid(backend, args, opts, recordid):

    if not recordid or recordid < 1:
        vprint('\nAbort, RecordID is invalid', args)
        sys.exit(-1)

    rule = get_recording_rule(backend, args, recordid)

    if not rule:
        return False

    return remove_record_rule(backend, args, opts, rule)


def remove_record_title(backend, args, opts):
    for rule in get_recording_rules(backend, args):
        if rule['Title'] == args['title']:
            remove_record_rule(backend, args, opts, rule)
            

def remove_manual_record_rule(backend, args, opts, starttime):
    if args['chanid']:
        chanid = args['chanid']
    else:
        chanid = get_chanid(backend, args['sourceid'], args['channum'])
        
    if not chanid:
        vprint('\nNeed chanid or sourceid and channum.', args)
        sys.exit(-1)

    if not starttime:
        vprint('\nNeed starttime', args)
        sys.exit(-1)

    recordid = get_recording_ruleid(backend, args, chanid, starttime)
    if not recordid:
        return False

    rule = get_recording_rule(backend, args, recordid)
    
    if not rule:
        vprint('Could not find a recording rule for recordid {}.'
               .format(recordid), args)
        return False
    else:
        if rule['SearchType'] != 'Manual Search':
            vprint('Found recording rule, but it is not "manual":'
                    .format(recording_rule_str(rule)), args)
            return False
        
    return remove_record_rule(backend, args, opts, rule)


# TODO: Fix for non hour blocks
def remove_manual_24x7(backend, args, opts):
    if not args['type']:
        vprint('Record type requried.', args)
        return False

    global localtz

    # First Saturday in January, for a 7-day/week schedule
    saturday = WEEKDAYAFTER(datetime(2018, 1, 1, tzinfo=localtz), 5)
    duration = 60 * 60

    for hour in list(range(24)):
        start = saturday.replace(hour=hour)
        remove_manual_record_rule(backend, args, opts, start.isoformat())

    return True
    

def remove_manual_record(backend, args, opts):

    if args['type'] == 'All':
        return remove_manual_24x7(backend, args, opts)
    else:
        return remove_manual_record_rule(backend, args, opts, args['starttime'])


def get_upcoming(backend, args):
    endpoint = 'Dvr/GetUpcomingList'

    if args['all']:
        rest = 'ShowAll=true'
    else:
        rest = ''

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest)
    except RuntimeError as error:
        sys.exit('\nFatal error: "{}"'.format(error))

    return resp_dict['ProgramList']


def program_flags_str(flgs):
    '''
    Convert the decimal flags to a printable string. From:
    libs/libmyth/programtypes.h. The </> print for values that
    haven't been defined here yet (and maybe should be.)
    '''
    strlst = []
    if flgs & (0x00fff):
        strlst.append('<')
    if flgs & (1 << 12):
        strlst.append('Rerun')
    if flgs & (1 << 13):
        strlst.append('Dup')
    if flgs & (1 << 14):
        strlst.append('React')
    if flgs & (0xf8000):
        strlst.append('>')
    return ', '.join(strlst)


def print_program_details(backend, program, args):
    '''
    Print a single program's information. Apply the --title and --chanid
    filters to select limited sets of recordings. Exit False if the
    --days limit is reached.
    '''

    global localtz
    global WIDTH

    matched = 0

    inputname= program['Recording']['EncoderName']
    title    = program['Title']
    subtitle = program['SubTitle']
    flags    = int(program['ProgramFlags'])
    chanid   = int(program['Channel']['ChanId'])

    startts  = datefromisostr(program['Recording']['StartTs'])
    startstr = startts.astimezone(localtz).isoformat()[:19]

    status   = int(program['Recording']['Status'])
    recid    = program['Recording']['RecordedId']

    statusstr = util.rec_status_to_string(backend=backend,
                                          rec_status=status)

    if args['current'] and statusstr != 'Recording' and statusstr != 'Recorded':
        return False, matched

    if int(recid) == 0:
        recid = ''

    if ((startts - utcnow).days >= args['days']):
        return False, matched

#    print('{}'.format(program))

    if ((args['title'] == '' or re.search(args['title'], title, re.IGNORECASE))
        and (args['chanid'] is None or args['chanid'] == chanid)):

        matched += 1
        print('{id:{id_width}} '
              '{inp:{inp_width}} '
              '{chanid:^{chanid_width}} '
              '{start:{start_width}}  {title:{title_width}} '
              '{sub:{sub_width}}  {status:{status_width}} {flags}'
              .format(id = recid, id_width = WIDTH['id'],
                      inp = inputname, inp_width = WIDTH['input'],
                      chanid = chanid, chanid_width = WIDTH['chanid'],
                      start = startstr, start_width = WIDTH['start'],
                      title = title, title_width = WIDTH['title'],
                      sub = subtitle, sub_width = WIDTH['subtitle'],
                      status = statusstr, status_width = WIDTH['status'],
                      flags = program_flags_str(flags)))

    return True, matched


def print_upcoming(backend, args):
    global WIDTH

    upcoming = get_upcoming(backend, args)
    count = int(upcoming['TotalAvailable'])
    programs = upcoming['Programs']

    if args['debug']:
        print('Debug: Upcoming recording count = {}'.format(count))

    if count < 1:
        vprint('\nNo upcoming recordings found.\n', args)
        sys.exit(0)

    for program in programs:
        WIDTH['id'] = max(WIDTH['id'], len(program['Recording']['RecordedId']))
        WIDTH['chanid'] = max(WIDTH['chanid'],
                              len(program['Channel']['ChanId']))
        WIDTH['title'] = max(WIDTH['title'], len(program['Title'].strip()))
        WIDTH['subtitle'] = max(WIDTH['subtitle'],
                                len(program['SubTitle'].strip()))
        startts  = datefromisostr(program['Recording']['StartTs'])
        startstr = startts.astimezone(localtz).isoformat()[:19]
        WIDTH['start'] = max(WIDTH['start'], len(startstr))
        WIDTH['end'] = max(WIDTH['end'], len(program['EndTime']))
        WIDTH['input'] = max(WIDTH['input'],
                             len(program['Recording']['EncoderName']))
        statusstr = util.rec_status_to_string(backend=backend,
                                     rec_status=program['Recording']['Status'])
        WIDTH['status'] = max(WIDTH['status'], len(statusstr))

    print('\nPrinting {} days of upcoming programs sorted by StartTime'
          .format(args['days']))
    print('\n{yellow}{id:{id_width}} {input:{input_width}} '
          '{chanid:{chanid_width}} {start:{start_width}}  {title:{title_width}} '
          '{sub:{subtitle_width}}  {status:{status_width}} {flags} {white}'
          .format(yellow=YELLOW,
                  id='Id', id_width = WIDTH['id'],
                  input='Input', input_width = WIDTH['input'],
                  chanid='ChanID', chanid_width = WIDTH['chanid'],
                  start='StartTime', start_width = WIDTH['start'],
                  title='Title', title_width = WIDTH['title'],
                  sub='SubTitle', subtitle_width = WIDTH['subtitle'],
                  status='Status', status_width = WIDTH['status'],
                  flags='Flags', white=WHITE))

    matched = 0
    for program in programs:
        result, cnt = print_program_details(backend, program, args)
        if not result:
            break
        matched += cnt

    if args['current']:
        print('\n  Total Currently Recording Programs: {}'.format(matched))
    else:
        print('\n  Total Upcoming Programs: {}'.format(matched))

    
def query_recordedid(backend, args, opts):
    endpoint = 'Dvr/RecordedIdForKey'

    Id = int
    dt = datefromisostr(args['starttime'])
    # Convert to UTC
    start = dt.astimezone(tz=timezone.utc)
    startstr = "{}".format(start.isoformat().replace('+00:00', 'Z'))

    rest = 'ChanId={}&StartTime={}'.format(args['chanid'], startstr)
    key = ('ChanId: {} StartTime: {}'.
           format(args['chanid'], startstr))

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeWarning as error:
        sys.exit('Abort, Unable to query RecordingId for: {}. Warning was: {}.'
                 .format(key, error))
    except RuntimeError as error:
        vprint('\nFatal API Error response: {}\n'.format(error), args)
        print(traceback.format_exc())
        return False

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['int'], str):
            Id = int(resp_dict['int'])
            if Id >= 0:
                vprint('RecordingId {} for "{}".'.format(Id, key), args)
            else:
                vprint('Failed to find RecordingId for "{}"'.format(key), args)
                return None
        else:
            vprint('Expected a "int: int" dictionary response, but got {}'
                   .format(resp_dict), args)
            return None
    except:
        print(traceback.format_exc())
        return None

    return Id


def stop_recordingid(backend, args, opts):
    endpoint = 'Dvr/StopRecording'

    if args['recordid']:
        Id = args['recordid']
    else:
        Id = query_recordedid(backend, args, opts)

    if not Id:
        vprint('Invalid RecordedId.', args)
        return False

    rest = 'RecordedId={}'.format(Id)

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeWarning as error:
        sys.exit('Abort, Unable to stop recording with Id: {}. Warning was: {}.'
                 .format(id, error))
    except RuntimeError as error:
        vprint('\nFatal API Error response: {}\n'.format(error), args)
        print(traceback.format_exc())
        return False

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if str2bool(resp_dict['bool']):
                vprint('RecordingId "{}" has been stopped.'.format(Id), args)
            else:
                vprint('Failed to stop RecordingId "{}"'.format(Id), args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
        return False

    return True

        
def reactivate_recordingid(backend, args, opts):
    endpoint = 'Dvr/ReactivateRecording'

    if args['recordid']:
        Id = args['recordid']
    else:
        Id = query_recordedid(backend, args, opts)

    if not Id:
        vprint('Invalid RecordedId.', args)
        return False

    rest = 'RecordedId={}'.format(Id)

    opts['wrmi'] = args['wrmi']

    try:
        resp_dict = backend.send(endpoint=endpoint, rest=rest, opts=opts)
    except RuntimeWarning as error:
        sys.exit('Abort, Unable to reactivate recording with Id: {}. '
                 'Warning was: {}.'.format(Id, error))
    except RuntimeError as error:
        vprint('\nFatal API Error response: {}\n'.format(error), args)
        print(traceback.format_exc())
        sys.exit(-1)

    opts['wrmi'] = False

    try:
        if isinstance(resp_dict, dict) and isinstance(resp_dict['bool'], str):
            if str2bool(resp_dict['bool']):
                vprint('Recorded Id {} has been reactivated.'.format(Id), args)
            else:
                vprint('Failed to reactivate recording with Id: "{}"'
                       .format(Id), args)
                return False
        else:
            vprint('Expected a "bool: bool" dictionary response, but got {}'
                   .format(resp_dict), args)
            return False
    except:
        print(traceback.format_exc())
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

    args = process_command_line()

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

    if args['group'] == 'add':
        if not args['title']:
            sys.exit('\nTitle for new rule is required.\n')

        if (int(args['manual']) > 0):
            return record_manual(backend, args, opts)
        else:
            if schedule_already_exists(backend, args, opts):
                vprint('\nRule for: "{}" already exists.'
                       .format(args['title']), args)
                return False
            return record_title(backend, args, opts)

    if args['group'] == 'remove':
        if (int(args['manual']) > 0):
            return remove_manual_record(backend, args, opts)
        elif args['recordid']:
            return remove_record_ruleid(backend, args, opts, args['recordid'])
        elif args['title']:
            return remove_record_title(backend, args, opts)
        else:
            vprint('Could not figure out type of recording rule to remove.',
                   args)
            return False

    if args['group'] == 'stop':
        stop_recordingid(backend, args, opts)

    if args['group'] == 'reactivate':
        reactivate_recordingid(backend, args, opts)

    if args['group'] == 'upcoming':
        print_upcoming(backend, args)

    if args['sources']:
        print_sources(backend, args)
    elif args['channels']:
        print_channels(backend, args)
    elif args['rules']:
        print_recording_rules(backend, args)
    elif args['templates']:
        print_templates(backend, args)
        

if __name__ == '__main__':
    main()

# vim: set expandtab tabstop=4 shiftwidth=4 smartindent noai colorcolumn=80
