#!/usr/bin/env python3

'''
sudo pip3 install streamlink
'''

from streamlink import Streamlink, StreamError, PluginError, NoPluginError
import argparse
from argparse import RawDescriptionHelpFormatter
import threading
import datetime
import sys
import errno
from subprocess import Popen, PIPE
from queue import Queue, Empty
from threading  import Thread
import signal
import fcntl
import os
import io
import traceback
import time
from select import select
import shlex

quiet = True
running = True


# The following logging code shamelessly copied from mythhdhrrecorder
#
# Logging is "complicated" because (a) we are running
# in python3, so as of now the existing MythTV logging
# class is not available, and (b), the existing MythTV
# logging class has not been updated for more recent
# logging changes (i.e. it does not support the dblog
# changes, nor systemd-journal logging), and (c) one
# cannot log to stdout in any case (stdout has been
# stolen by the transport stream for the External
# Recoder).  So, while we will try to import the
# (hoped for) eventual new version of the logging class,
# we will provide an adequate 'stub' for now (probably
# 90% borrowed from the existing MythTV.logging class).

try:
    import MythTV.logging
except ImportError:

    import syslog
    try:
        import systemd.journal
    except:
        ...

    class LOGMASK(object):
        ALL         = 0b111111111111111111111111111
        MOST        = 0b011111111110111111111111111
        NONE        = 0b000000000000000000000000000

        GENERAL     = 0b000000000000000000000000001
        RECORD      = 0b000000000000000000000000010
        PLAYBACK    = 0b000000000000000000000000100
        CHANNEL     = 0b000000000000000000000001000
        OSD         = 0b000000000000000000000010000
        FILE        = 0b000000000000000000000100000
        SCHEDULE    = 0b000000000000000000001000000
        NETWORK     = 0b000000000000000000010000000
        COMMFLAG    = 0b000000000000000000100000000
        AUDIO       = 0b000000000000000001000000000
        LIBAV       = 0b000000000000000010000000000
        JOBQUEUE    = 0b000000000000000100000000000
        SIPARSER    = 0b000000000000001000000000000
        EIT         = 0b000000000000010000000000000
        VBI         = 0b000000000000100000000000000
        DATABASE    = 0b000000000001000000000000000
        DSMCC       = 0b000000000010000000000000000
        MHEG        = 0b000000000100000000000000000
        UPNP        = 0b000000001000000000000000000
        SOCKET      = 0b000000010000000000000000000
        XMLTV       = 0b000000100000000000000000000
        DVBCAM      = 0b000001000000000000000000000
        MEDIA       = 0b000010000000000000000000000
        IDLE        = 0b000100000000000000000000000
        CHANNELSCAN = 0b001000000000000000000000000
        SYSTEM      = 0b010000000000000000000000000
        TIMESTAMP   = 0b100000000000000000000000000

    class LOGLEVEL(object):
        ANY         = -1
        EMERG       = 0
        ALERT       = 1
        CRIT        = 2
        ERR         = 3
        WARNING     = 4
        NOTICE      = 5
        INFO        = 6
        DEBUG       = 7
        UNKNOWN     = 8

    class LOGFACILITY(object):
        KERN        = 1
        USER        = 2
        MAIL        = 3
        DAEMON      = 4
        AUTH        = 5
        LPR         = 6
        NEWS        = 7
        UUCP        = 8
        CRON        = 9
        LOCAL0      = 10
        LOCAL1      = 11
        LOCAL2      = 12
        LOCAL3      = 13
        LOCAL4      = 14
        LOCAL5      = 15
        LOCAL6      = 16
        LOCAL7      = 17

    class MythLog(LOGLEVEL, LOGMASK, LOGFACILITY):

        def __init__(self, module='pythonbindings', db=None):
            self._module = module
            self._db = db
            self._parseinput = self._noop

        def _noop(self):
            pass

        def _initlogger(self):
            self._initlogger = self._noop
            self._MASK = LOGMASK.GENERAL
            self._LEVEL = LOGLEVEL.DEBUG
            self._LOGSTREAM = None
            self._logwrite = self._logdummy
            self._QUIET = 1
            self._DBLOG = False
            self._SYSLOG = None
            self._lock = threading.Lock()
            self._parseinput()

        def _logdummy(self, mask, level, message, detail=None):
            return

        def _logstream(self, mask, level, message, detail=None):
            self._LOGSTREAM.write('{0} {3} [{1}] {2} ' \
                    .format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                      os.getpid(), self._module,
                      ['!','A','C','E','W','N','I','D'][level]) + 
                      message + (' -- {0}'.format(detail) if detail else '') + '\n')
            self._LOGSTREAM.flush()
            return

        def _logsyslog(self, mask, level, message, detail=None):
            syslog.syslog(message + (' -- {0}'.format(detail) if detail else ''))
            return

        def _logjournal(self, mask, level, message, detail=None):
            systemd.journal.sendv('MESSAGE=' + message + (' -- {0}'.format(detail) if detail else ''),
                                  'PRIORITY=' + str(level),
                                  'SYSLOG_PID=' + str(os.getpid()),
                                  'SYSLOG_IDENTIFIER=' + self._module)
            return

        def log(self, mask, level, message, detail=None):
            self._initlogger()
            if level > self._LEVEL:
                return
            if not mask&self._MASK:
                return
            if self._QUIET > 1:
                return

            with self._lock:
                self._logwrite(mask, level, message, detail)
            #
            # In this stub we do not support logging to the database
            # (database logging is deprecated, and probably a bad
            # idea on most real world implementations anyway)
            #
            #if self._DBLOG:
            #    self._logdatabase(mask, level, message, detail)

        def _argparseinput(self):
            opts = self._parser.parse_args()
            if opts.quiet:
                self._QUIET = opts.quiet
            if opts.enable_dblog:
                self._DBLOG = opts.enable_dblog
            if opts.loglevel:
                self._LEVEL = getattr(self, opts.loglevel)
                if self._LEVEL is None:
                    self._LEVEL = LOGLEVEL.INFO
            if opts.verbose:
                vlist = ('IMPORTANT', 'GENERAL', 'RECORD', 'PLAYBACK', 'CHANNEL',
                    'OSD', 'FILE', 'SCHEDULE', 'NETWORK', 'COMMFLAG', 'AUDIO',
                    'LIBAV', 'JOBQUEUE', 'SIPARSER', 'EIT', 'VBI', 'DATABASE',
                    'DSMCC', 'MHEG','UPNP','SOCKET','XMLTV','DVBCAM','MEDIA',
                    'IDLE', 'CHANNELSCAN', 'EXTRA', 'TIMESTAMP')
                for v in opts.verbose.upper().split(','):
                    if v in ('ALL', 'MOST', 'NONE'):
                        self._MASK = getattr(self, v)
                    elif v in vlist:
                        self._MASK |= getattr(self, v)
                    elif (len(v) > 2) and (v[0:2] == 'NO'):
                        if v[2:] in vlist:
                            self._MASK &= self._MASK^getattr(self, v[2:])
            if opts.logpath:
                if self._SYSLOG is not None:
                    self._SYSLOG.closelog()
                    self._SYSLOG = None
                if self._LOGSTREAM is not None:
                    self._LOGSTREAM.close()
                    self._LOGSTREAM = None
                fn = os.path.join(opts.logpath, '{0}.{1}.{2}.log'.format(self._module,
                                    datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                                    os.getpid()))
                self._LOGSTREAM = io.open(fn, 'w')
                self._logwrite = self._logstream
            if opts.syslog:
                if self._LOGSTREAM is not None:
                    self._LOGSTREAM.close()
                    self._LOGSTREAM = None
                self._logwrite = self._logsyslog
                self._SYSLOG = opts.syslog
                syslog.openlog(self._module, logoption=syslog.LOG_PID|syslog.LOG_NDELAY, facility=getattr(syslog, 'LOG_' + opts.syslog))
            if opts.journal:
                if self._SYSLOG is not None:
                    self._SYSLOG.closelog()
                    self._SYSLOG = None
                if self._LOGSTREAM is not None:
                    self._LOGSTREAM.close()
                    self._LOGSTREAM = None
                self._logwrite = self._logjournal

        def loadArgParse(self, parser):
            self._parser = parser
            self._parseinput = self._argparseinput
            parser.add_argument('--quiet', '-q', action='count', default=0, dest='quiet',
                        help='Run quiet.')
            parser.add_argument('--verbose', '-v', type=str.lower, dest='verbose', default='general',
                        help='Specify log verbosity')
            parser.add_argument('--enable-dblog', action='store_true', dest='enable_dblog', default=False,
                        help='Specify logging to the database.')
            parser.add_argument('--loglevel', action='store', type=str.upper, dest='loglevel', default='info',
                        choices=['ANY', 'EMERG', 'ALERT', 'CRIT', 'ERR', 'WARNING', 'NOTICE', 'INFO', 'DEBUG', 'UNKNOWN'],
                        help='Specify log verbosity, using standard syslog levels.')
            parser.add_argument('--logpath', action='store', type=str, dest='logpath',
                        help='Specify directory to log to, filename will be automatically decided.')
            parser.add_argument('--syslog', action='store', type=str.upper, dest='syslog',
                        choices=['AUTH', 'AUTHPRIV', 'CRON', 'DAEMON', 'KERN', 'LPR', 'MAIL', 'NEWS',
                                 'SYSLOG', 'USER', 'UUCP', 'LOCAL0', 'LOCAL1', 'LOCAL2', 'LOCAL3',
                                 'LOCAL4', 'LOCAL5', 'LOCAL6', 'LOCAL7'],
                        help='Specify syslog facility to log to.')
            parser.add_argument('--systemd-journal', action='store_true', dest='journal', default=False,
                        help='Specify systemd-journald logging.')

        def __call__(self, mask, level, message, detail=None):
            self.log(mask, level, message, detail)


def exit(msg):
    log(MythLog.GENERAL|MythLog.RECORD, MythLog.NOTICE, msg)
    sys.exit()

    
def sig_handler(signum, frame):
    log(MythLog.GENERAL|MythLog.RECORD, MythLog.WARNING, 
        "handling signal: {}\n".format(signum))
    sys.stderr.write("handling signal: {}\n".format(signum))
    sys.stderr.flush()

    global running
    running = False

    
class StreamlinkPlayer(object):
    def __init__(self, log):
        global quiet

        self.log = log
        self.fd = None
        self.buf_size = 188 * 200

        cmd = ['ffmpeg']

        if quiet:
            cmd += ['-hide_banner', '-nostats', '-loglevel', 'panic']

        cmd += ['-re', '-i', 'pipe:', '-codec', 'copy', '-f', 'mpegts', 'pipe:']
        args = shlex.split(' '.join(cmd))
        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.INFO,
                 'Running "{}"'.format(args))

        self.ffmpeg = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        self.q = Queue()
        self.t = Thread(target=self.read_stream, args=(self.ffmpeg.stdin,
                                                       self.q))
        self.t.daemon = True

        fl = fcntl.fcntl(self.ffmpeg.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.ffmpeg.stdout, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def exit(self, msg):
        self.stop()
        exit(msg)

    def stop(self):
        # Close the stream
        if self.fd:
            self.fd.close()
        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.NOTICE, 'Stopped')

    def play(self, stream):
        global running
        
        # Attempt to open the stream
        try:
            self.fd = stream.open()
        except StreamError as err:
            self.exit("Failed to open stream: {0}".format(err))

        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.INFO, "Opened stream.")
        self.t.start()
        
        frame = b''

        while running:
            try:
                readable, writable, exceptional = select([self.ffmpeg.stdout,
                                                          self.ffmpeg.stderr],
                                                         [], [], 10)
                for fd in readable:
                    if fd is self.ffmpeg.stdout:
                        frame = fd.read()
                        if frame:
                            self.log(MythLog.RECORD, MythLog.DEBUG,
                                'processed {} bytes'.format(len(frame)))
                            sys.stdout.buffer.write(frame)
                        else:
                            self.log(MythLog.RECORD, MythLog.DEBUG,
                                'Empty frame'.format(len(frame)))
                            time.sleep(0.1)
                            if self.ffmpeg.poll() is None:
                                running = False
                    elif fd is self.ffmpeg.stderr:
                        msg = fd.readline()
                        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.WARNING,
                            'Process error: {}'.format(msg))
                    else:
                        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.WARNING,
                            'unexpected fd {}'.format(fd))

            except:
                print(traceback.format_exc(), file=sys.stderr)


        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.NOTICE,
                 'Stopping FFmpeg')
        
        try:
            os.killpg(os.getpgid(self.ffmpeg.pid), signal.SIGTERM)
        except:
            ...
        self.ffmpeg.wait()

        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.NOTICE,
                 'FFmpeg finished')

    def read_stream(self, out, queue):
        global running

        data = b''

        # Attempt to read data from the stream
        while running:
            try:
                data += self.fd.read(self.buf_size)
            except io as err:
                self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.WARNING,
                    'I/O error: {}'.format(err))
            except IOError as err:
                out.close()
                self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.ERR,
                    'Failed to read data from stream: {0}'.format(err))
                running = False
                return
            except OSError as err:
                out.close()
                self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.ERR,
                    'OSError: {0}'.format(err))
                running = False
                return
            except BrokenPipeError as err:
                out.close()
                self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.ERR,
                    'Broken pipe: {0}'.format(err))
                running = False
                return

            # If data is empty it's the end of stream
            if not data:
                out.close()
                source.emit('end-of-stream')
                running = False
                return

            try:
                self.log(MythLog.RECORD, MythLog.DEBUG,
                    'read {} bytes'.format(len(data)))
                out.write(data)
                data = b''
            except IOError as e:
                if e.errno == errno.EPIPE:
                    self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.ERR,
                        'Broken pipe (ffmpeg died?): {0}'.format(err))
                else:
                    self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.ERR, e)
                running = False

        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.NOTICE,
                 'Streamlink done.')

    def on_eos(self, bus, msg):
        # Stop playback on end of stream
        vprint('on_eos')
        self.log(MythLog.GENERAL|MythLog.RECORD, MythLog.NOTICE,
                 'Streamlink EoS.')
        self.stop()

    def on_error(self, bus, msg):
        # Print error message and exit on error
        error = msg.parse_error()[1]
        self.exit(error)


def main():

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    # Instantiate logging
    appname = os.path.basename(sys.argv[0])
    log = MythLog(os.path.basename(sys.argv[0]))

    examples = ('\nExamples:\n'
                '\tList current recording rules:\n'
                '\t\t{0} --rules\n'
                '\tList current sources:\n'
                '\t\t{0} --sources\n'
                '\tList channels for a source:\n'
                '\t\t{0} --channels <sourceid>\n'
                .format(appname)
    )

    parser = argparse.ArgumentParser(description='Streamlink a video',
                                     formatter_class=RawDescriptionHelpFormatter,
                                     epilog='Default values are in ().\n'
                                     .format(appname, examples))

    mandatory = parser.add_argument_group('required arguments')

    parser.add_argument('--url', type=str, required=True,
                        metavar='<URL>', help='backend hostname')

    QUALITY = ( 'best', 'worst')
    values = ', '.join(QUALITY)
    parser.add_argument('--quality', type=str, required=False,
                             choices=(QUALITY), metavar='<type>',
                             default='best',
                             help='Card <type> [{}] (%(default)s)'
                             .format(values))

    parser.add_argument('--version', action='version', version='%(prog)s 0.11')

    log.loadArgParse(parser)

    args = vars(parser.parse_args())

    log(MythLog.GENERAL|MythLog.RECORD, MythLog.INFO, 'mythtv-stream starting, args: {0}'.format(' '.join(sys.argv[1:])))

    url     = args['url']
    quality = args['quality']

    # Create the Streamlink session
    streamlink = Streamlink()

    # Enable logging
    streamlink.set_loglevel('debug')
    streamlink.set_logoutput(sys.stderr)

    # Attempt to fetch streams
    try:
        streams = streamlink.streams(url)
    except NoPluginError:
        exit("Streamlink is unable to handle the URL '{0}'".format(url))
    except PluginError as err:
        exit('Plugin error: {0}'.format(err))

    if not streams:
        exit('No streams found on URL "{0}"'.format(url))

    # Look for specified stream
    if quality not in streams:
        exit('Unable to find "{0}" stream on URL "{1}"'.format(quality, url))

    # We found the stream
    stream = streams[quality]

    # Create the player and start playback
    player = StreamlinkPlayer(log)

    # Blocks until playback is done
    player.play(stream)


if __name__ == "__main__":
    main()    
