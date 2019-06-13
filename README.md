
# Python scripts for configuring MythTV #

## Prerequisites ##
Grab utilties from:
https://github.com/billmeek/MythTVServicesAPI/tree/master/dist

i.e.
```
mkdir -p ~/src/Myth/Python
cd ~/src/Myth/Python
git clone https://github.com/billmeek/MythTVServicesAPI.git
cd MythTVServicesAPI
sudo -H pip3 install dist/mythtv_services_api-0.1.9-py3-none-any.whl
```

## Overview ##
### mythtv-initialize.py ###
Used to configure a new installation of mythbackend.  '''Incomplete''' -- do not use.

For example usage:
```
mythtv-initialize --help
```

### mythtv-source.py ###
Configure MythTV "inputs" (source, card, input)

For example usage:
```
mythtv-source --help
mythtv-source.py source --help
mythtv-source.py card --help
mythtv-source.py input --help
```

### mythtv-record.py ###
Manage MythTV recording rules (add, remove, list upcoming, stop, reactivate)

For example usage:
```
mythtv-record.py --help
mythtv-record.py add --help
mythtv-record.py remove --help
mythtv-record.py upcoming --help
mythtv-record.py stop --help
mythtv-record.py reactivate --help
```

### mythtv-monitor ###
Monitor MythTV 'events' (listens to mythbackend websocket)

## Usage ##

All of these scripts have a '--wrmi' option, which must be specified to indicate that you actually want the script to perform the requested action -- this is a safety measure.

### Add a new source ###
```
mythtv-source.py --wrmi source --name "Twitch" --grabber "None"
```

Issues the 'source' option to create a source named "Twitch" with no grabber.  It will print out something like "3 added for source "Twitch".  That '3' is the source Id.  If running in bash, you could script this with something like:
```
result=$(./mythtv-source.py --wrmi source --name "Twitch" --grabber "None")
echo ${result}
if [ $? -ne 0 ]
then
    exit
fi

set -- $result
source=$1
echo "Sourceid: ${source}"
```

### Add a new card ###
```
mythtv-source.py --wrmi card --type EXTERNAL --device "/usr/bin/mythexternrecorder --conf /home/myth/etc/twitch.conf"
```

Issues the "card" option to create a new card of type EXTERNAL which uses the mythexternrecorder application.  It will print out something like "4 added for card "/usr/bin/mythexternrecorder --conf /home/myth/etc/twitch.conf".  The '4' is the card Id.

### Add a new input for a card ###
```
mythtv-source.py --wrmi input --cardid 4 --sourceid 3 --inputtype MPEG2TS --name "Twitch7"
```

Issues the "input" option to create a new input associated with card Id 4 and source Id 3.  Each input should have a unique name, in this example "Twitch7".
It is possible to have more than one input per card, but for MonitorIQ that is almost never what you want.
You will need a card and input for each 'device' you want to record from simultaneously.  If you want to record 16 channels at the same time, you will need to define 16 cards and inputs.

### Populating the channels ###
For each source, you need to populate the channels database (mythconverg.channel).  Pick any of the cards associated with the source, and use the mythtv-setup command to scan than input for channels:

```
mythtv-setup -v chanscan:debug,channel:debug,record --loglevel info --scan 4 --freq-std extern --scan-non-interactive
```

### List the configured MythTV sources ###
```
mythtv-source.py --sources
```

### List the channels for a source ###
```
mythtv-source.py --channels 3
```

### Add a 24/7 "manual" recording rule ###
```
mythtv-record.py add --manual --type All --chanid 80017 --title "Manual Record 80017"
```

When the '--manual' option is given, using '--type' All results in a 24/7 schedule.  See the associated program help for more examples.



