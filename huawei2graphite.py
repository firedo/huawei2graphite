#!/usr/bin/python3

# Copyright 2021 (c) firedo
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Huawei LTE API
from huawei_lte_api.Client import Client
from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Connection import Connection

from twisted.internet import task, reactor
from twisted.internet.defer import setDebugging
import datetime
import time
import logging
import logging.handlers
import re
import lockfile
import signal
import os
import sys
from pathlib import Path
import getopt
import graphyte
import requests
import json
import daemon

from twisted.internet import task, reactor
from pathlib import Path
from twisted.internet.defer import setDebugging








# Handle signals
def handle_signal (sig, _frame):
    signals = dict((k, v) for v, k in signal.__dict__.items() if v.startswith('SIG'))
    app.logger.info ("Received signal (%s)" % signals[sig])

    if sig == signal.SIGUSR1:
        app.logger.warning("Setting log level to 'DEBUG'")
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.warning ("Going to exit.")
        app.stop = True
        time.sleep(3)
        reactor.callFromThread(reactor.stop)

# Return float if it can be converted into float
def floatOrNull(val):
    try:
        return float(val)
    except:
        return None

# Return 'int' if it can be converted into 'int'
def intOrNull(val):
    try:
        return int(val)
    except:
        return None

class StreamToLogger(object):
    # Fake file-like stream object that redirects writes to a logger instance.
    def __init__(self, logger, log_level=logging.ERROR):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

class App:

    def __init__(self):
        self.daemonize = False
        self.reboot = False
        self.locationTag = False
        self.stop = False
        self.sendData2Graphite = False
        self.level = logging.INFO
        self.LoggingSetupDone = False
        self.enableLoop = False
        self.sendTestData = False

        self.connection = False

        self.testData = dict()
        self.testData['nrrsrp_value'] = -100
        self.testData['nrrsrp_min'] = -100
        self.testData['nrrsrp_max'] = -76
        
        self.testData['nrrsrq_value'] = -30
        self.testData['nrrsrq_min'] = -30
        self.testData['nrrsrq_max'] = -0
        
        self.testData['nrsinr_value'] = -5
        self.testData['nrsinr_min'] = -5
        self.testData['nrsinr_max'] = 35
        
        self.testData['rsrp_value'] = -100
        self.testData['rsrp_min'] = -100
        self.testData['rsrp_max'] = -76
        
        self.testData['rsrq_value'] = -30
        self.testData['rsrq_min'] = -30
        self.testData['rsrq_max'] = -0
        
        self.testData['sinr_value'] = -5
        self.testData['sinr_min'] = -5
        self.testData['sinr_max'] = 35
        
        self.testData['rssi_value'] = -94
        self.testData['rssi_min'] = -94
        self.testData['rssi_max'] = -65
        
        self.testData['ltedlfreq_value'] = 1500 # Multiplied by 1000
        self.testData['ltedlfreq_min'] = 1500 # Multiplied by 1000
        self.testData['ltedlfreq_max'] = 2000 # Multiplied by 1000
        
        self.testData['lteulfreq_value'] = 1500 # Multiplied by 1000
        self.testData['lteulfreq_min'] = 1500 # Multiplied by 1000
        self.testData['lteulfreq_max'] = 2000 # Multiplied by 1000
        
        self.testData['dlfrequency_value'] = 10 # Multiplied by 1000
        self.testData['dlfrequency_min'] = 10 # Multiplied by 1000
        self.testData['dlfrequency_max'] = 60 # Multiplied by 1000
        
        self.testData['ulfrequency_value'] = 10 # Multiplied by 1000
        self.testData['ulfrequency_min'] = 10 # Multiplied by 1000
        self.testData['ulfrequency_max'] = 60 # Multiplied by 1000
        
        # Explains below regexp ###               =|<|>| dB(m)  | (k)Hz  
        self.signalData_strip_regexp = "(=|<|>|(dB(m)?)|((k)?Hz))" # These characters and unit of measurements will be stripped from the signal data values

        self.config = dict()
        
        # Default values for the default config file that will be written if it doesn't exist already.
        self.default_config = {
            "router_hostname": "192.168.8.1",
            "router_username": "admin",
            "router_password": "Unique per router. Check the router password tag or behind the router itself.",
            "graphite_hostname": "localhost",
            "graphite_port": 2003,
            "graphite_prefix": "huawei2graphite",
            "graphite_protocol": "http",
            "graphite_http_port": 8080,
            "graphite_url_hostname": "localhost",
            "logfile": "/tmp/huawei2graphite.log",
            "loopInterval": 30.0,
            "eventTag_LocationChanged": "huawei2graphite_location_changed",
            "eventTag_CellIDchanged": "huawei2graphite_cell_id_changed",
            # These data keys will be collected from the Huawei LTE/5G modem, converted to float and their values sent to Graphite
            # 5G (non-standalone aka. with 4G as a anchor): ["rsrp", "rsrq", "rssi", "sinr", "lteulfreq", "ltedlfreq", "ulfrequency", "dlfrequency", "nrrsrp", "nrrsrq", "nrsinr"]
            "signalDataKeys": ["rsrp", "rsrq", "rssi", "sinr", "lteulfreq", "ltedlfreq", "ulfrequency", "dlfrequency", "nrrsrp", "nrrsrq", "nrsinr"],

        }

        # Set config and cache locations
        self.homeFolder = str(Path.home())
        self.dataFolder = self.homeFolder + '/.config/huawei2graphite/'
        self.configFileName = "config.json"
        self.configFilePath = self.dataFolder + self.configFileName
        self.cacheFolder = self.homeFolder + '/.cache/huawei2graphite/'
        self.saveDataFileName = "data.json"
        self.saveDataFilePath = self.cacheFolder + self.saveDataFileName

    # Create folder if it doesn't exist
    def createFolder(self, folder):
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                return True
            except Exception as e:
                print("ERROR: Unable to create the '{}' directory. Exception: {}".format(folder, str(e)))
                sys.exit(15)
        return True

    # Save dict as JSON file
    def saveJSONfile(self, filename, data):
        try:
            with open(filename, 'w',) as saveFile:
                json.dump(data, saveFile, sort_keys = True, indent = 4, ensure_ascii = False)
                saveFile.close()
            return True
        except Exception as e:
            print("WARNING: Unable to write the '{}' JSON file. Exception: {}".format(filename, str(e)))
        return False

    # Load JSON data from file and return it, on failure return empty dict()
    def loadJSONfile(self, filename):
        try:
            if os.path.exists(filename):
                with open(filename, 'r',) as loadFile:
                    return json.load(loadFile)
        except Exception as e:
            print("WARNING: Unable to read the '{}' JSON file. Exception: {}".format(filename, str(e)))
        return dict()

    # Setup logger (and log to file)
    def setup_logging(self):
        os.umask(0o22)
        self.logger = logging.getLogger()

        self.logger.setLevel(self.level)
        formatter = logging.Formatter('%(asctime)s [%(process)d] %(levelname)s: %(message)s','%Y-%m-%d %H:%M:%S')
        try:
            loghandler = logging.handlers.WatchedFileHandler(self.config['logfile'])
        except IOError:
            print("Could not open logfile ({0})".format(self.config['logfile']))
            return False

        loghandler.setFormatter(formatter)
        self.logger.addHandler(loghandler)

        if self.daemonize:
           # Redirect stdout and stderr to logger, using StreamToLogger object that handles writes
            sys.stdout = StreamToLogger(self.logger, logging.INFO)
            sys.stderr = StreamToLogger(self.logger, logging.ERROR)

        else:
            # Set up a second loghandler, that writes to stderr
            loghandler2 = logging.StreamHandler(sys.stderr)
            loghandler2.setFormatter(formatter)
            self.logger.addHandler(loghandler2)

        return True

    def usage(self):
        print("Usage: {} [-h] [-l|-r|-d|-t|-o] [] [-i secs] [-v[v]...]".format(os.path.realpath(__file__)))
        print("-h = help/usage")
        print("-l = enable loop")
        print("-r = reboot device")
        print("-d = daemonize")
        print("-t = Generate test data instead with a 'test' path. Increment values on every loop run, but keep them between min/max values.")
        print('-o "Location Text" = add an Event with the text value to Graphite.')
        print("-s = enable sending data to Graphite (by default this program just prints the value).")
        print("-i X = set the loop interval to X seconds (default is 30.0). keep in mind that it will be ran every X seconds always, regardless of the last running time.")
        print("-v = more verbose (add to get more verbose)")
        sys.exit(2)

    def main(self):

        # Create data/cache folders if they don't exist
        self.createFolder(self.dataFolder)
        self.createFolder(self.cacheFolder)

        # Load config and earlier saved data
        self.config = self.loadJSONfile(self.configFilePath)
        self.saveData = self.loadJSONfile(self.saveDataFilePath)
        

        # Check that config data exists
        try:
            if not (self.config):
                if os.path.exists(self.configFilePath):
                    print("ERROR: the '{}' config file exists, but it is empty or corrupt. Exiting.".format(self.configFilePath))
                    sys.exit(14)
                else:
                    print("ERROR: the '{}' config file does not exist, creating new config file with default values. You need to modify at least the router password.".format(self.configFilePath))
                    self.saveJSONfile(self.configFilePath, self.default_config)
                    sys.exit(13)
        except Exception as e:
                print("ERROR: Failed to check the presence of the 'self.config' dict(). Exception: {}".format(str(e)))
                sys.exit(14)

        # Check that the default password has been changed
        try:
            if (self.config['router_password'] == self.default_config['router_password']):
                print("ERROR: the '{}' config file still has the default router password. Please change it first.".format(self.configFilePath))
                sys.exit(15)
        except Exception as e:
            print("ERROR: Failed to check if the default password has been changed. 'self.config[router_password]' & 'self.default_config[router_password]' dict(). Exception: {}".format(str(e)))
            sys.exit(16)

        # Generate the Graphite URL
        try:
            self.graphite_url = self.config['graphite_protocol'] + '://' + self.config['graphite_url_hostname'] + ':' + str(self.config['graphite_http_port'])
        except Exception as e:
            print("ERROR: Failed to combine the config variables 'graphite_protocol', 'graphite_url_hostname' & 'graphite_http_port' to 'self.graphite_url'. Exception: {}".format(str(e)))
            sys.exit(17)

        # Start loop (or run loop only once).
        if app.daemonize or app.enableLoop:
            theLoopTask = task.LoopingCall(self.theLoop)
            theLoopTask.start(self.config['loopInterval'])
            reactor.run()
        else:
            self.theLoop()

    # Create events at Graphite to mark changes in the timeline
    def create_graphite_event(self, event_description, tags, event_data):
        tags_string = " ".join(str(x) for x in tags)  # Converting dictionary to comma-separated string, as we have an array but Graphite expects multiple tags comma-separated like "a,b,c" or "a b c" (space-separated)
        event = {"what": event_description, "tags": tags_string, "data": event_data}
        try:
            requests.post(self.graphite_url +"/events/", data=json.dumps(event), timeout=1)
        except Exception as e:
            self.logger.error('Error while creating an Graphite Event. Exception: {}'.format(str(e)))
            return False
        return True

    # The main loop
    def theLoop(self):
        # Setup logging if not done already
        if not self.LoggingSetupDone:
            if not self.setup_logging():
                print("Unable to setup logging")
            # Set logger verbosity level
            if verboseLevel >= 3:
                log_level = logging.DEBUG
                setDebugging(True)
            elif verboseLevel == 2:
                log_level = logging.INFO
            elif verboseLevel == 1:
                log_level = logging.WARN
            else:
                log_level = logging.ERROR
            app.logger.setLevel(log_level)
            self.LoggingSetupDone = True

        # Stop loop if we got the signal to quit
        if self.stop:
            reactor.stop()
            return False

        self.logger.info("")
        self.logger.info("#####################################################")
        self.logger.info("")


        ########################################################################################################################################################################

        # Create an Graphite Event and exit
        if (app.locationTag):
            self.stop = True
            try:
                if self.create_graphite_event("Location changed", [ self.config['eventTag_LocationChanged'] ], 'Location: {}'.format(self.locationTag)):
                    self.logger.info("Successfully created the event.")
                else:
                    self.logger.error("Failed to create the event.")
                    return False
            except Exception as e:
                self.logger.error("Failed to create the event. Exception: {}".format(str(e)))
                return False
            return True

        ########################################################################################################################################################################

        # Reboot the Huawei LTE/5G modem and exit
        if (app.reboot):
            self.stop = True
            try:
                self.logger.info("# Connecting...")
                self.connection = AuthorizedConnection('http://{}:{}@{}/'.format(self.config['router_username'], self.config['router_password'], self.config['router_hostname'])) # Login required even for signal data
                client = Client(self.connection)
                self.logger.info("Done.")

                self.logger.warning("# Rebooting...")
                self.logger.info(client.device.reboot())
                self.logger.warning("# Done.")
            except Exception as e:
                self.logger.error("Unable to reboot the device. Exception: {}".format(str(e)))
                return False
            return True

        ########################################################################################################################################################################
        # Initialize Graphyte (for sending data)

        # Get current time
        ts = time.time()

        if (self.sendData2Graphite):
            try:
                # Init #       hostname,   port,    prefix, timeout, interval
                graphyte.init(self.config['graphite_hostname'], self.config['graphite_port']) # Skip prefix, timeout and interval (no data?)
            except Exception as e:
                self.logger.error("Unable to initialize Graphyte (for sending metrics to Graphite). Exception: {}".format(str(e)))

        ########################################################################################################################################################################
        # Create & send test data to Graphite and exit
        if self.sendTestData:
            for signalDataKey in self.config['signalDataKeys']:
                try:
                    if (self.testData[signalDataKey + '_value'] < self.testData[signalDataKey + '_max']):
                        self.testData[signalDataKey + '_value'] += 1
                    else:
                        self.testData[signalDataKey + '_value'] = self.testData[signalDataKey + '_min']
                except Exception as e:
                    self.logger.error("Exception: {}".format(str(e)))

            for metric, value in sorted(self.testData.items()):
                
                # Replace dots with underscores
                safe_metric = metric.replace('.', '_')
            
                # Build the metric path from general prefix, 'test' and key name (metric)
                metric_path = self.config['graphite_prefix'] + ".test." + safe_metric

                # Only act on _values, skip originals
                if bool(re.match('.*_value$', metric)):
                        if bool(re.match('.*lfreq.*', metric)):
                            value = value * 1000

                        if (self.sendData2Graphite):
                            sendDataText = "Sending *test* data"
                        else:
                            sendDataText = "Simulating (not sending) *test* data"

                        self.logger.info("%s for '%s'. ts=%d => %s" % (sendDataText, metric_path, ts, datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')))
                        self.logger.debug("Value: '{}'".format(value))

                        if (self.sendData2Graphite):
                            try:
                                # send data - metric_path,    value, [timestamp, tags (dict)]
                                graphyte.send(metric_path, value, ts)
                            except Exception as e:
                                self.logger.error("Unable to send the test data to Graphite. Exception: {}".format(str(e)))
                                return False
                else:
                    # Skipping original values, as these can't be saved as strings.
                    pass
            self.logger.warning("Success. Loop done. Waiting max. {} seconds for the next run.".format(self.config['loopInterval']))
            return True

        ################################################################################
        # Get real data and send it to Graphite

        # Check if logged in or login timed out...
        try:
            if self.connection.logged_in == False or self.connection._is_login_timeout() == True:
                self.logger.info("Not already logged in OR login has timed out. We need to (re)connect.")
                raise Exception('not_logged_in')

            self.logger.debug("#self.connection.logged_in: {}".format(self.connection.logged_in))
            self.logger.debug("#self.connection._is_login_timeout(): {}".format(self.connection._is_login_timeout()))
        # ... if not, (re)connect
        except:
            try:
                self.logger.info("# Connecting...")
                self.connection = AuthorizedConnection('http://{}:{}@{}/'.format(self.config['router_username'], self.config['router_password'], self.config['router_hostname'])) # Login required even for signal data
                self.logger.info("# Done.")
            except Exception as e:
                self.logger.warning("Failed on 1st try to connect OR we got the already logged in exception.")
                self.logger.warning("Exception: {}".format(str(e)))
        # Try to get data from the API...
        try:
            client = Client(self.connection)
            APIsignalData = client.device.signal()
        except Exception as e1:
            # ... If that failed,reconnecting first and then try again.
            try:
                self.logger.info("# Connecting...")
                self.connection = AuthorizedConnection('http://{}:{}@{}/'.format(self.config['router_username'], self.config['router_password'], self.config['router_hostname'])) # Login required even for signal data
                self.logger.info("# Done.")

                client = Client(self.connection)
                APIsignalData = client.device.signal()
            except Exception as e2:
                self.logger.warning("Failed on 2nd try to connect OR we got the already logged in exception.")
                self.logger.warning("Exception (e1): {}".format(str(e1)))
                self.logger.warning("Exception (e2): {}".format(str(e2)))
                return False

        # Get values for the signalDataKeys (variables) from the returned API data, convert the string values to floats (returns None aka. null if it fails), ...
        # ... strip specific extra characters (check self.signalData_strip_regexp) and save the original value as well.
        signalData2Graphite = dict()
        for signalDataKey in self.config['signalDataKeys']:
            try:
                signalData2Graphite[signalDataKey + '_original'] = APIsignalData[signalDataKey]
                signalData2Graphite[signalDataKey + '_value'] = floatOrNull(re.sub(r"{}".format(self.signalData_strip_regexp), "", APIsignalData[signalDataKey]))
            except:
                pass

        # Get current time
        ts = time.time()

        # Check if Cell ID changed
        cell_id_changed = False
        try:
            if (self.saveData['latest_cell_id']):
                pass
            else:
                cell_id_changed = True
        except:
            self.saveData['latest_cell_id'] = ''
            cell_id_changed = True
        try:
            if (APIsignalData['cell_id'] != self.saveData['latest_cell_id']):
                self.logger.info("*** CELL ID changed.")
                cell_id_changed = True
        except:
            pass

        # Create Cell ID changed Graphite Event
        failed_to_send_cell_id_changed = False
        if (cell_id_changed):
            if (self.sendData2Graphite):
                sendDataText = "Creating an Event"
            else:
                sendDataText = "Simulating an Event creation"

            self.logger.info("%s ('%s'). ts=%d => %s" % (sendDataText, self.config['eventTag_CellIDchanged'], ts, datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')))
            self.logger.debug("Cell ID: {}/{} (Old/New)".format(self.saveData['latest_cell_id'], APIsignalData['cell_id']))

            if (self.sendData2Graphite):
                try:
                    if self.create_graphite_event("Cell ID changed", [self.config['eventTag_CellIDchanged'], "cell_id_{}".format(APIsignalData['cell_id'])], 'Cell ID: {}/{} (Old/New)'.format(self.saveData['latest_cell_id'], APIsignalData['cell_id'])):
                        self.logger.warning("Successfully created the event.")

                        # Save the Cell ID change to a variable and the JSON file
                        self.saveData['latest_cell_id'] = APIsignalData['cell_id']
                        self.saveJSONfile(self.saveDataFilePath, self.saveData)
                    else:
                        self.logger.error("Failed to create the event in Graphite. Unknown error.")
                        failed_to_send_cell_id_changed = True
                except Exception as e:
                    self.logger.error("Failed to create the event in Graphite. Exception: {}".format(str(e)))
                    failed_to_send_cell_id_changed = True

        # Go through all the values and send them to Graphite
        for extra_prefix in {"all", 'by_cell_id.' + APIsignalData['cell_id']}: # Send the data with the extra prefixes 'all' and by the Cell ID (double data stored, but you can later on filter the data per Cell ID as well)
            for metric, value in sorted(signalData2Graphite.items()):
                
                # Replace dots with underscores
                safe_metric = metric.replace('.', '_')
            
                # Build the metric path from general prefix, extra prefix and key name (metric)
                metric_path = self.config['graphite_prefix'] + "." + extra_prefix + "." + safe_metric

                # Only act on _values, skip originals
                if bool(re.match('.*_value$', metric)):
                        haveOriginalValue = True
                        try:
                            # Get original value
                            original_value_key = re.sub(r"_value", "_original", metric)
                            original_value = signalData2Graphite[original_value_key]
                        except Exception as e:
                            haveOriginalValue = False
                            self.logger.warning("Unable to get the original value. Exception: {}".format(str(e)))


                        if self.sendData2Graphite:
                            sendDataText = "Sending data"
                        else:
                            sendDataText = "Simulating (not sending) data"

                        self.logger.info("%s for '%s'. ts=%d => %s" % (sendDataText, metric_path, ts, datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')))

                        if haveOriginalValue:
                            self.logger.debug("Value: '{}' (Original_value: '{}')".format(value, original_value))
                        else:
                            self.logger.debug("Value: '{}'".format(value))

                        if self.sendData2Graphite:
                            try:
                                # send data - metric_path,    value, [timestamp, tags (dict)]
                                graphyte.send(metric_path, value, ts)
                            except Exception as e:
                                self.logger.error("Unable to send the data to Graphite. Exception: {}".format(str(e)))
                                return False
                else:
                    # Skipping original values, as these can't be saved as strings.
                    pass
        


        # Save latest cell ID only if we successfully sent the data to Graphite
        if (self.sendData2Graphite and not failed_to_send_cell_id_changed):
            self.saveData['latest_cell_id'] = APIsignalData['cell_id']
            self.saveJSONfile(self.saveDataFilePath, self.saveData)
        self.logger.warning("Success. Loop done. Waiting max. {} seconds for the next run.".format(self.config['loopInterval']))
        return True

    # End: def theLoop():
    ########################################################################################################################################################################
# End: class App:
########################################################################################################################################################################


if __name__ == "__main__":

    app = App()

    verboseLevel = 0
    
    # Parse the command-line arguments
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hdsrlto:i:v")
    except getopt.GetoptError as e:
        print("ERROR: Unknown command-line argument: {}".format(str(e)))
        print("Arguments: {}".format(sys.argv[1:]))
        sys.exit(4)
    except Exception as e:
        print("ERROR: Unknown error with an command-line argument. Exception: {}".format(str(e)))
        print("Arguments: {}".format(sys.argv[1:]))
        sys.exit(4)
    for opt, arg in opts:
        if opt == '-h': # Show usage/help
            app.usage()
            sys.exit(0)
        elif opt == '-d': # Daemon
            app.daemonize = True
        elif opt == '-s': # Enable sending data
            app.sendData2Graphite = True
        elif opt == '-r': # Reboot
            app.reboot = True
        elif opt == '-l': # Loop
            app.enableLoop = True
        elif opt == '-t': # Generate/send test data
            app.sendTestData = True
        elif opt == '-o': # Create an Location Event with an custom value
            # Disallow single-quotes as they break the existing single-quotes
            if bool(re.search("'", arg)):
                print('ERROR: Disallowed characters in the argument: "{}"'.format(arg))
                print("All characters are allowed, except single-quotes (').")
                sys.exit(7)
            else:
                app.locationTag = arg
        elif opt == '-i': # Loop interval
            try:
                app.config['loopInterval'] = float(arg)
            except:
                print("ERROR: {} is NOT a number.".format(arg))
                app.usage()
                sys.exit(6)
        elif opt == '-v': # Raise verbose level
            verboseLevel += 1

        # Make sure that there are no conflicting arguments
        if (app.enableLoop):
            if (app.daemonize):
                print("ERROR: Loop '-l' is NOT allowed with daemonize '-d'")
                sys.exit(8)
            if (app.reboot):
                print("ERROR: Loop '-l' is NOT allowed with reboot '-r'")
                sys.exit(9)
            if (app.locationTag):
                print("ERROR: Loop '-l' is NOT allowed with location '-o'")
                sys.exit(10)
        if (app.daemonize):
            if (app.reboot):
                print("ERROR: Daemonize '-l' is NOT allowed with reboot '-r'")
                sys.exit(11)
            if (app.locationTag):
                print("ERROR: Daemonize '-l' is NOT allowed with location '-o'")
                sys.exit(12)

    if app.daemonize:
        context = daemon.DaemonContext()
        context.signal_map = {
            signal.SIGTERM: handle_signal,
            signal.SIGINT: handle_signal,
            signal.SIGUSR1: handle_signal
        }
        print("Sending the process to a background daemon, check the log file for more info.")
        with context:
            app.main()
            app.logger.info("Done. Exiting.")

    else:
        signal.signal (signal.SIGTERM, handle_signal)
        signal.signal (signal.SIGINT, handle_signal)
        signal.signal (signal.SIGUSR1, handle_signal)
        app.main()
        app.logger.info("Done. Exiting.")

