#!/usr/bin/env python3
import argparse
import asyncio
import concurrent.futures
import time
import csv
try:
    from .libreVNA import libreVNA, RAWVNA
    from .tdr import TDR
except:
    from libreVNA import libreVNA, RAWVNA
    from tdr import TDR

import datetime
import os


# run with
# LibreVNA-GUI --no-gui --port 19542


class VNAGPR(object):
    calibration = os.environ.get('CALIBRATION', '/Users/ian/projects/SOLT 1.00M-3.00G 303pt.cal')

    vna = None

    def __init__(self, use_raw=False):
        self.use_raw = use_raw

    async def connect(self):
        if self.use_raw:
            self.vna = RAWVNA('localhost', 6969)
        else:
            # Create the control instance

            self.vna = libreVNA('localhost', 19542)
            await self.vna.connect()

            # Quick connection check (should print "LibreVNA-GUI")
            print(await self.vna.query("*IDN?"))

            # Make sure we are connecting to a device (just to be sure, with default settings the LibreVNA-GUI auto-connects)
            await self.vna.cmd(":DEV:CONN")
            dev = await self.vna.query(":DEV:CONN?")
            if dev == "Not connected":
                print("Not connected to any device, aborting")
                exit(-1)
            else:
                print("Connected to "+dev)


    async def scan(self):
        if self.use_raw:
            """ todo impliment scan / setup on RAW"""
            return
        # Simple trace data extraction

        # switch to VNA mode, setup the sweep parameters
        print("Setting up the sweep...")
        await self.vna.cmd(":DEV:MODE VNA")
        await self.vna.cmd(":VNA_CAL:LOAD {}".format(self.calibration))
        await self.vna.cmd(":VNA_CAL:TYPE SOLT")
        await self.vna.cmd(":VNA:SWEEP FREQUENCY")
        await self.vna.cmd(":VNA:STIM:LVL 0")
        await self.vna.cmd(":VNA:ACQ:IFBW 10000")
        await self.vna.cmd(":VNA:ACQ:AVG 1")
        await self.vna.cmd(":VNA:ACQ:POINTS 303")
        await self.vna.cmd(":VNA:AQC 1")
        #vna.cmd(":VNA:AQQuisition:AVG 1")
        #vna.cmd(":VNA:FREQuency:SPAN 1")
        await self.vna.cmd(":VNA:FREQuency:START 10000000")
        await self.vna.cmd(":VNA:FREQuency:STOP 3000000000")

        # wait for the sweep to finish
        print("Waiting for the sweep to finish...")
        while await self.vna.query(":VNA:ACQ:FIN?") == "FALSE":
            await asyncio.sleep(0.1)

    async def close(self):
        if self.vna:
            return await self.vna.close()

    async def writedata(self, output, run_seconds=None):

        if self.vna is None:
            await self.connect()
            await self.scan()

        loop = asyncio.get_event_loop()

        # grab the data of trace S11
        print("Reading trace data...")
        self.directory = 'data/{}'.format(output)
        if os.path.exists(self.directory):
            raise Exception("Directory exists")

        os.makedirs(self.directory)
        start_time = datetime.datetime.utcnow()

        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:


            while True:
                start = datetime.datetime.utcnow()
                if self.use_raw:
                    S21 = await self.vna.read_trace()
                else:
                    data = await self.vna.query(":VNA:TRACE:DATA? S21")
                    S21 = self.vna.parse_trace_data(data)
                end = datetime.datetime.utcnow()
                total_seconds = (end - start).total_seconds()
                print("took {} seconds".format(total_seconds))
                print(output)

                def write_file():
                    #todo use more efficient async file writes
                    with open('{}/{}'.format(self.directory, start.isoformat()),'w') as e:
                        writer = csv.writer(e)

                        for row in S21:
                            freq, real, imag = row[0], row[1].real, row[1].imag
                            writer.writerow((freq,real,imag))

                tasks.append(loop.run_in_executor(executor, write_file))

                time_ran = datetime.datetime.utcnow() - start_time
                if total_seconds < 0.01:
                    await asyncio.sleep(0.01)

                if run_seconds and time_ran.total_seconds() > run_seconds:
                    print("running for {} seconds, stopping capture".format(run_seconds))
                    break
            await asyncio.gather(*tasks)


    async def run(self):
        await self.connect()
        await self.scan()


def main():
    parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("-o", "--output", type=str,
                    help="ouput file folder ")

    parser.add_argument("-t", "--time", type=int, default=None,
                    help="time to write data")

    parser.add_argument("-p", "--pipeline",  action="store_true",
                    help="run tdr  pipeline ( only works with time set)")
    parser.add_argument("-r", "--raw",  action="store_true",
                    help="Use RAWVNA protocol")


    args = parser.parse_args()
    output = args.output

    try:
        GPR = VNAGPR(use_raw=args.raw)
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(GPR.writedata(args.output, args.time))

        if args.time and args.pipeline:
            print("stopping data collection, running pipeline")
            tdr = TDR(use_csv=True)
            tdr.listFolder(GPR.directory + '/', GPR.directory +'o')
    finally:

        loop.run_until_complete(GPR.close())


if __name__=="__main__":
    main()
