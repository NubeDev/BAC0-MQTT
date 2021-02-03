import BAC0
from BAC0.scripts.Lite import Lite
import paho.mqtt.publish as publish
import time
import json
import requests
import traceback
from math import isnan 

PROG_ROOT = '.'
CONFIG_FILE = PROG_ROOT + "/config.json"

def create_msg(topic, payload):
    msg = {
        'topic': topic,
        'payload': payload
    }
    return msg

def print_flush(string):
    print(string, flush=True)

# Open config file and place in config_obj variable
# if no file found, create new file
try:
    with open(CONFIG_FILE) as cf:
        config_obj = json.load(cf)
except FileNotFoundError as e:
    print_flush('Config file not found, the default config file will be generated in the current directory.')

    config_obj = {
        "host_ip":"10.130.1.220/24",
        "find_devices":False,
        "devices":[
            { "ip":"10.130.1.205/24", "device_id":1234 },
            { "ip":"10.130.1.239/24", "device_id":1234 }
        ],
        "mqtt":{
            "host":"nube-io.com",
            "port":1883,
            "base_topic":"TEST/"
        },
        "loop_time":30
    }

    with open(CONFIG_FILE, "w") as cf:
        cf.write(json.dumps(config_obj))

bacnet = Lite(config_obj['host_ip'])

# If the find_deivces config variable is true, search for any
# available devices using the whois method.
if config_obj['find_devices']:
    print_flush('Searching for devices...')
    config_obj['devices'] = []
    device_dict = bacnet.whois()
    time.sleep(2)
    if device_dict:
        for addr, id in device_dict.keys():
            device = {
                'ip': addr,
                'device_id': id
            }
            config_obj['devices'].append(device)
            print_flush('Found device at ' + addr)
    else:
        print_flush('No devices found! Goodbye!')

# If no devices are given or no devices were found,
# skip the loop and exit the script
if config_obj['devices']:
    while True:
        print_flush("Starting Loop")

        with open(PROG_ROOT + "/.heartbeat",'w+') as f:
            import datetime
            f.write(str(datetime.datetime.now()))

        msgs = []
        start_time = time.time()
        try:
            for a_device in config_obj['devices']:
                print_flush('Connecting to ' + a_device['ip'] + ' ...')
                device = BAC0.device(a_device['ip'], a_device['device_id'], bacnet, poll=0)

                if not(isinstance(device, BAC0.core.devices.Device.DeviceDisconnected)):
                    print_flush(device.properties.address + ' Connected')

                    topic = config_obj['mqtt']['base_topic'] + 'log/info'
                    payload = json.dumps({
                        'msg_type': 'connceted',
                        'msg': 'Device Connected',
                        'device_addr': device.properties.address
                    })

                    msg = create_msg(topic, payload)

                    msgs.append(msg)

                    for point in device.points:
                        #topic = config_obj['mqtt']['base_topic'] + 'device/' + str(device.properties.device_id) + '/point/' + point.properties.name
                        #topic = config_obj['mqtt']['base_topic'] + str(device.properties.device_id) + '/' + point.properties.name
                        topic = config_obj['mqtt']['base_topic'] + point.properties.name

                        value = point.value
                        if point.value == 'active':
                            value = 'true'
                        elif value == 'inactive':
                            value = 'false'
                        elif isinstance(point.value, float) and isnan(point.value):
                            value = 0;
                        payload = value

                        msg = create_msg(topic, payload)

                        msgs.append(msg)

                    requests.post(config_obj['red_ip'] if 'red_ip' in config_obj else 'http://localhost:1880/red',data=json.dumps(msgs))

                    publish.multiple(msgs, hostname=config_obj['mqtt']['host'], port=config_obj['mqtt']['port'])
                    print_flush(device.properties.address + ' Published')
                else:
                    print_flush(device.properties.address + ' Offline')

                    topic = config_obj['mqtt']['base_topic'] + 'log/warn'
                    payload = json.dumps({
                        'msg_type': 'offline',
                        'msg': 'Device Offline',
                        'device_addr': device.properties.address
                    })

                    publish.single(topic, payload, hostname=config_obj['mqtt']['host'], port=config_obj['mqtt']['port'])

        except Exception as e:
            print(traceback.print_exc())

        time_elapsed = time.time() - start_time

        if config_obj['loop_time'] - time_elapsed > 0:
            sleep_time = config_obj['loop_time'] - time_elapsed
        else:
            sleep_time = 0

        print_flush("---- Loop took %.2f seconds ----" % time_elapsed)
        print_flush("--- Sleeping for %.2f seconds ---" % sleep_time)
        time.sleep(sleep_time)
