#!/usr/bin/env python3
import json
import sys
import re
import subprocess
import time
from lxml import etree

SPEED_CONFIG_FILE = 'fanspeed.json'
FAN_CONTROL_STATE_STRING = '[gpu:{}]/GPUFanControlState={}'
TARGET_FAN_SPEED_STRING = '[fan-{}]/GPUTargetFanSpeed={}'

class FanController(object):
    num_of_gpus = 0
    fanspeed_config = None

    @classmethod
    def reset_fan_control_state(self):
        sys.stderr.write('Received SIGINT, resetting fan control state...\n')
        for i in range(self.num_of_gpus):
            subprocess.run(['nvidia-settings', '-a', FAN_CONTROL_STATE_STRING.format(i, 0)], stdout=subprocess.PIPE)
        sys.stderr.write('Done, quit.\n')
        sys.exit(0)

    @classmethod
    def get_num_of_gpus(self):
        result = subprocess.run(['nvidia-smi', '-q', '-x'], stdout=subprocess.PIPE)
        doc = etree.fromstring(result.stdout.decode())
        num_gpus = doc.xpath('/nvidia_smi_log/attached_gpus/text()')[0]
        self.num_of_gpus = int(num_gpus)
        return int(num_gpus)
    
    def set_fan_control_state(self):
        sys.stderr.write('Setting fan control state...\n')
        for i in range(self.num_of_gpus):
            subprocess.run(['nvidia-settings', '-a', FAN_CONTROL_STATE_STRING.format(i, 1)], stdout=subprocess.PIPE)

    def get_smi_data(self, gpu_index):
        result = subprocess.run(['nvidia-smi', '-q', '-x', '-i', '{}'.format(gpu_index)], stdout=subprocess.PIPE)
        doc = etree.fromstring(result.stdout.decode())
        return doc

    def get_temp_of_gpu(self, doc):
        temp = doc.xpath('/nvidia_smi_log/gpu/temperature/gpu_temp/text()')[0]
        temp = int(re.sub(r'[^0-9]*', '', temp))
        return temp

    def get_fanspeed_of_gpu(self, doc):
        speed = doc.xpath('/nvidia_smi_log/gpu/fan_speed/text()')[0]
        speed = int(re.sub(r'[^0-9]*', '', speed))
        return speed
        
    def get_name_of_gpu(self, doc):
        name = doc.xpath('/nvidia_smi_log/gpu/product_name/text()')[0]
        return str(name)

    def get_fanspeed_config(self):
        config_file = open(SPEED_CONFIG_FILE, 'r')
        if not config_file:
            sys.stderr.write('Can not read config file.\n')
            sys.exit(0)
        json_config = json.loads(''.join(config_file.readlines()))
        config_file.close()
        self.fanspeed_config = json_config

    def __init__(self):
        self.get_num_of_gpus()
        sys.stderr.write('Number of GPUs found on this system: {}\n'.format(self.num_of_gpus))
        self.get_fanspeed_config()
        sys.stderr.write('Read fan speed config done.\n')
        self.set_fan_control_state()

    def set_target_fanspeed_of_gpu(self, gpu_index, speed):
        subprocess.run(['nvidia-settings', '-a', TARGET_FAN_SPEED_STRING.format(gpu_index, speed)], stdout=subprocess.PIPE)

    def mainloop(self):
        sys.stderr.write('Starting main loop...\n')
        while True:
            for i in range(self.num_of_gpus):
                doc = self.get_smi_data(i)
                temp = str(self.get_temp_of_gpu(doc))
                speed = self.get_fanspeed_of_gpu(doc)
                target_speed = self.fanspeed_config[temp]
                gpu_name = self.get_name_of_gpu(doc)
                if(speed != target_speed):
                    print('GPU{}: {}, temp {}, fan speed {}, target speed {}'.format(i, gpu_name, temp, speed, target_speed))
                    self.set_target_fanspeed_of_gpu(i, target_speed)
            time.sleep(1)

if __name__ == '__main__':
    try:
        controller = FanController()
        controller.mainloop()
    except KeyboardInterrupt:
        controller.reset_fan_control_state()
