huawei2graphite
=========

## Description:
_Huawei Signal Data to Graphite - Get 4G (& 5G) signal data from Huawei LTE/5G modems (using Huawei's API) and sent it to Graphite for visualization of statistics_

In daemon/loop mode it will run until stopped manually and generates (and sends) data every X seconds to Graphite (default destination: localhost on TCP port 2003).

Data will be sent to Graphite using the below example paths:
```
huawei2graphite.all.rssi
huawei2graphite.all.rsrp
...
huawei2graphite.by_cell_id.[Cell ID].rssi
huawei2graphite.by_cell_id.[Cell ID].rsrp
...

Test data:
huawei2graphite.test.rssi
...
```

## Requirements:
* Graphite (for ex. [Docker](https://hub.docker.com/r/graphiteapp/graphite-statsd/))
* Python 3
* ``` pip install -r requirements.txt ```

## Usage:
```sh
huawei2graphite.py [-h] [-l|-r|-d|-o] [] [-i secs] [-v[v]...]
-h = help/usage
-l = enable loop (generate [and send] data every interval [-i] seconds)
-r = reboot device
-d = daemonize
-t = Generate test data instead with a 'test' path. Increment values on every loop run, but keep them between min/max values.
-o "Location Text" = add an Event with the text value to Graphite.
-s = enable sending data to Graphite (by default this program just prints the value).
-i X = set the loop interval to X seconds (default is 30.0). keep in mind that it will be ran every X seconds always, regardless of how long the last running time was.
-v = more verbose (add multiple of these to get more output)
```

NOTE: First-time run creates the required ~/.config/huawei2graphite.json JSON configuration. You need to at least change the router's password, as that is unique per device.

Examples:
* Run in background (log file /tmp/huawei2graphite.log), logging level INFO, enable sending data to Graphite & run every 30 seconds:
```
huawei2graphite.py -d -vv -s -i 60
```
* Run in foreground, logging level DEBUG, generate test data, enable loop and don't send data to Graphite (simulate only).
```
huawei2graphite.py -vvv -t -l
```
* Reboot modem
```
huawei2graphite.py -r
```
	

## License

Apache License, version 2.0.

A copy of the license can be found in the 'LICENSE' file and [online](http://www.apache.org/licenses/LICENSE-2.0)
