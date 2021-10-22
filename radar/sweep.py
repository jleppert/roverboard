#!/usr/bin/env python3
import argparse

import time
import csv
from libreVNA import libreVNA
import datetime
import os

class VNAGPR(object):
    calibration = os.environ.get('CALIBRATION', '/Users/ian/projects/1-6g.cal')
    def __init__(self):
        pass

    def connect(self):
        # Create the control instance
        self.vna = libreVNA('localhost', 19542)

        # Quick connection check (should print "LibreVNA-GUI")
        print(self.vna.query("*IDN?"))

        # Make sure we are connecting to a device (just to be sure, with default settings the LibreVNA-GUI auto-connects)
        self.vna.cmd(":DEV:CONN")
        dev = self.vna.query(":DEV:CONN?")
        if dev == "Not connected":
            print("Not connected to any device, aborting")
            exit(-1)
        else:
            print("Connected to "+dev)

    def scan(self):
        vna = self.vna
        # Simple trace data extraction

        # switch to VNA mode, setup the sweep parameters
        print("Setting up the sweep...")
        vna.cmd(":DEV:MODE VNA")
        vna.cmd(":VNA_CAL:LOAD {}".format(self.calibration))
        vna.cmd(":VNA:SWEEP FREQUENCY")
        vna.cmd(":VNA:STIM:LVL 0")
        vna.cmd(":VNA:ACQ:IFBW 10000")
        vna.cmd(":VNA:ACQ:AVG 1")
        vna.cmd(":VNA:ACQ:POINTS 101")
        vna.cmd(":VNA:AQC 1")
        #vna.cmd(":VNA:AQQuisition:AVG 1")
        #vna.cmd(":VNA:FREQuency:SPAN 1")
        vna.cmd(":VNA:FREQuency:START 1000000000")
        vna.cmd(":VNA:FREQuency:STOP 2000000000")

        # wait for the sweep to finish
        print("Waiting for the sweep to finish...")
        while vna.query(":VNA:ACQ:FIN?") == "FALSE":
            time.sleep(0.1)

    def writedata(self, output):

        # grab the data of trace S11
        print("Reading trace data...")
        directory = 'data/{}'.format(output)
        if os.path.exists(directory):
            raise Exception("Directory exists")

        os.makedirs(directory)
        while True:
            start = datetime.datetime.utcnow()
            data = self.vna.query(":VNA:TRACE:DATA? S21")
            end = datetime.datetime.utcnow()
            print("took {} seconds".format((end - start).total_seconds()))
            S21 = self.vna.parse_trace_data(data)
            print(output)


            with open('{}/{}'.format(directory, start.isoformat()),'w') as e:
                writer = csv.writer(e)

                for row in S21:
                    freq, real, imag = row[0], row[1].real, row[1].imag
                    writer.writerow((freq,real,imag))
            time.sleep(0.025)

    def run(self):
        self.connect()
        self.scan()


def main():
    parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-o", "--output", type=str,
                    help="ouput file name for DZT, .DZT will be added")


    args = parser.parse_args()
    output = args.output
    GPR = VNAGPR()

    GPR.run()
    GPR.writedata(args.output)

if __name__=="__main__":
    main()
