#!/usr/bin/env python3
import argparse
import asyncio
import concurrent.futures
import time
import csv
try:
    from .libreVNA import libreVNA, libreVNAAsync
    from .tdr import TDR
except:
    from libreVNA import libreVNA, libreVNAAsync
    from tdr import TDR

import datetime
import os



# run with
# LibreVNA-GUI --no-gui --port 19542
class VNAGPR(object):
    calibration = os.environ.get('CALIBRATION', '/Users/ian/projects/SOLT 1.00M-3.00G 303pt.cal')
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
        vna.cmd(":VNA_CAL:TYPE SOLT")
        vna.cmd(":VNA:SWEEP FREQUENCY")
        vna.cmd(":VNA:STIM:LVL 0")
        vna.cmd(":VNA:ACQ:IFBW 10000")
        vna.cmd(":VNA:ACQ:AVG 1")
        vna.cmd(":VNA:ACQ:POINTS 303")
        vna.cmd(":VNA:AQC 1")
        #vna.cmd(":VNA:AQQuisition:AVG 1")
        #vna.cmd(":VNA:FREQuency:SPAN 1")
        vna.cmd(":VNA:FREQuency:START 10000000")
        vna.cmd(":VNA:FREQuency:STOP 3000000000")

        # wait for the sweep to finish
        print("Waiting for the sweep to finish...")
        while vna.query(":VNA:ACQ:FIN?") == "FALSE":
            time.sleep(0.1)

    def close(self):
        return self.vna.sock.close()

    async def writedata_async(self, output, run_seconds=None):

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
                data = self.vna.query(":VNA:TRACE:DATA? S21")
                end = datetime.datetime.utcnow()
                total_seconds = (end - start).total_seconds()
                print("took {} seconds".format(total_seconds))
                S21 = self.vna.parse_trace_data(data)
                print(output)

                def write_file():
                    with open('{}/{}'.format(self.directory, start.isoformat()),'w') as e:
                        writer = csv.writer(e)

                        for row in S21:
                            freq, real, imag = row[0], row[1].real, row[1].imag
                            writer.writerow((freq,real,imag))

                tasks.append(loop.run_in_executor(executor,write_file))

                time_ran = datetime.datetime.utcnow() - start_time
                if total_seconds < 0.01:
                    time.sleep(0.025)
                if run_seconds and time_ran.total_seconds() > run_seconds:
                    print("running for {} seconds, stopping capture".format(run_seconds))
                    break
            await asyncio.gather(*tasks)


    def writedata(self, output, run_seconds=None):

        # grab the data of trace S11
        print("Reading trace data...")
        self.directory = 'data/{}'.format(output)
        if os.path.exists(self.directory):
            raise Exception("Directory exists")

        os.makedirs(self.directory)
        start_time = datetime.datetime.utcnow()



        while True:
            start = datetime.datetime.utcnow()
            data = self.vna.query(":VNA:TRACE:DATA? S21")
            end = datetime.datetime.utcnow()
            total_seconds = (end - start).total_seconds()
            print("took {} seconds".format(total_seconds))
            S21 = self.vna.parse_trace_data(data)
            print(output)

            with open('{}/{}'.format(self.directory, start.isoformat()),'w') as e:
                writer = csv.writer(e)

                for row in S21:
                    freq, real, imag = row[0], row[1].real, row[1].imag
                    writer.writerow((freq,real,imag))
            time_ran = datetime.datetime.utcnow() - start_time

            if run_seconds and time_ran.total_seconds() > run_seconds:
                print("running for {} seconds, stopping capture".format(run_seconds))
                break

            if total_seconds < 0.01:
                time.sleep(0.025)

    def run(self):
        self.connect()
        self.scan()


class VNAGPRAsync(object):
    calibration = os.environ.get('CALIBRATION', '/Users/ian/projects/SOLT 1.00M-3.00G 303pt.cal')

    vna = None

    def __init__(self):
        pass

    async def connect(self):
        # Create the control instance

        self.vna = libreVNAAsync('localhost', 19542)
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

    async def writedata_async(self, output, run_seconds=None):

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
                data = await self.vna.query(":VNA:TRACE:DATA? S21")
                end = datetime.datetime.utcnow()
                total_seconds = (end - start).total_seconds()
                print("took {} seconds".format(total_seconds))
                S21 = self.vna.parse_trace_data(data)
                print(output)

                def write_file():
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

    parser.add_argument("-a", "--async",  action="store_true",
                    help="use async file writes")

    parser.add_argument("-p", "--pipeline",  action="store_true",
                    help="run tdr  pipeline ( only works with time set)")

    args = parser.parse_args()
    output = args.output
    try:

        if not args.async:
            print("not using async")
            GPR = VNAGPR()

            GPR.run()
            GPR.writedata(args.output, args.time)
        else:
            print("using async")
            GPR = VNAGPRAsync()
            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            loop.run_until_complete(GPR.writedata_async(args.output, args.time))

        if args.time and args.pipeline:
            print("stopping data collection, running pipeline")
            tdr = TDR(use_csv=True)
            tdr.listFolder(GPR.directory + '/', GPR.directory +'o')
    finally:
        if not args.async:
            GPR.close()
        else:
            loop.run_until_complete(GPR.close())


if __name__=="__main__":
    main()
