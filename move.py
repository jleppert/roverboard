# -*- encoding: utf-8 -*-
# Test environment: Python 3.6

import socket
import sys
import asyncio
import os
from simple_pid import PID

import RPi.GPIO as GPIO
import time

import logging

from radar.sweep import VNAGPR
from radar.tdr import TDR
import datetime

from concurrent.futures import ProcessPoolExecutor



logger = logging.getLogger(__name__)

# In direct connection mode, the default IP address of the robot is 192.168.2.1 and the control command port is port 40923.
host = os.environ.get("djihost", "127.0.0.1")



class RobotMove(object):
    process_executor = ProcessPoolExecutor(max_workers=1)

    robot_ip = host
    x = 0
    y = 0
    z = 0

    x_rel = 0
    y_rel = 0
    z_rel = 0

    #gpio config
    sprayer_output_pin = 13


    def __init__(self):
        """ Each robot move class can only have one running start task"""
        self.start_lock = asyncio.Lock()
        self.start_coro = None
        self.setup_gpio()


    def to_dict(self):
        data = {"x": self.x_rel, "y": self.y_rel, "z": self.z_rel,
                "is_running": self.start_lock.locked()}

        return data

    def setup_gpio(self):
        GPIO.setmode(GPIO.BOARD)  # BCM pin-numbering scheme from Raspberry Pi
        # set pin as an output pin with optional initial state of HIGH
        GPIO.setup(self.sprayer_output_pin, GPIO.OUT, initial=GPIO.LOW)

    async def run_sprayer(self, seconds=.1):
        try:
            GPIO.output(self.sprayer_output_pin, GPIO.HIGH)
            await asyncio.sleep(seconds)
            GPIO.output(self.sprayer_output_pin,GPIO.LOW)
        except Exception as e:
            logger.exception("GPIO failed")
        finally:
            GPIO.output(self.sprayer_output_pin, GPIO.LOW)


    async def connect(self):

        self.ctrl_reader, self.ctrl_writer = await asyncio.open_connection(self.robot_ip, 40923)
        self.event_reader, self.event_writer =  await asyncio.open_connection(self.robot_ip, 40925)
        self.ctrl_reader1, self.ctrl_writer1 = await asyncio.open_connection(self.robot_ip, 40923)

        self.pid_z = PID(1, 0.1, 0.05, setpoint=1)
        self.start_z = None

    async def send_command(self, command, read_socket=None, write_socket=None):
        read_socket = read_socket or self.ctrl_reader
        write_socket = write_socket or self.ctrl_writer
        print("send command ", command)
        write_socket.write((command + ';').encode("utf8"))
        try:
            result = await asyncio.wait_for(read_socket.read(1024), timeout=3.0)
        except asyncio.TimeoutError:
            print('timeout!')
            return None
        print(result)
        return result.decode().strip()

    async def read_events(self):
        print("read events coro")
        while True:
            data = await self.event_reader.read(4096)
            print(f'Received: {data.decode()!r}')
        print("exited read events coro")


    async def _get_position(self, read_socket, write_socket):
        position = await self.send_command("chassis position ?", read_socket=read_socket, write_socket=write_socket)
        print(position)
        try:
            self.x, self.y, self.z = [float(v) for v in position.split(' ')]
            if self.start_z is None:
                self.start_z = self.z

        except Exception as e:
            return
            import pdb; pdb.set_trace()

    async def _run_correction(self, read_socket, write_socket):
        await self._get_position(read_socket, write_socket)

        if (self.z) > 1 or (self.z) < -1:
            print("running correction")
            try:
                await self.send_command("chassis speed z {}".format(self.z * -1), read_socket=read_socket, write_socket=write_socket)
                await asyncio.sleep(0.8)
                await self.send_command("chassis speed z 0", read_socket=read_socket, write_socket=write_socket)
                await asyncio.sleep(1)
            except Exception as e:
                import pdb; pdb.set_trace()

    async def read_position_loop(self):
        while True:
            position = await self.send_command("chassis position ?", read_socket=self.ctrl_reader1, write_socket=self.ctrl_writer1)
            print("position loop", position)
            await asyncio.sleep(5)

    @staticmethod
    def write_tdr(name):
        try:
            tdr = TDR(use_csv=True)
            d = "data/{}".format(name)
            tdr.listFolder(d + '/', d+'o')
        except:
            logger.exception("Failed post proccessing job ")

    async def write_gpr_data(self, gpr, name, seconds):
        # TODO re-write GPR device opening to be peristent
        """ starts recording existing GPR session and converts TDR when complete in a thread"""
        await gpr.writedata(name, seconds)
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, self.write_tdr, name)

    async def record_gpr(self, seconds):
        # TODO keep persistent session open to GPR device
        """ starts processing GPR for specified number of seconds in another coro, which spawns a thread for TDR, returns before complete"""


        gpr = VNAGPR(use_raw=False)
        await gpr.run()
        name = datetime.datetime.utcnow().isoformat()

        task = asyncio.ensure_future(self.write_gpr_data(gpr, name, seconds))
        return task



    async def move(self, x=0, y=0, speed = 0.2, z=0, z_speed=30, record_gpr=False):

        """ impliments move to relative position based on velocity and track position"""
        if x and y:
            logger.warning("unable to move with both X and Y")

        if x:
            t = abs(x) / abs(speed)
            if x < 0:
                speed = -abs(speed)
            if record_gpr:
                gpr_task = await self.record_gpr(t)
            await self.send_command("chassis speed x {}".format(speed))
            await asyncio.sleep(t)
            await self.send_command("chassis speed x 0 ")
            if record_gpr:
                await gpr_task
            # todo track movement in real time as rover is moving in a single command
            self.x_rel += x

        elif y:
            t = abs(y) / abs(speed)
            if y < 0:
                speed = -abs(speed)

            await self.send_command("chassis speed y {}".format(speed))
            await asyncio.sleep(t)
            await self.send_command("chassis speed y 0")
            self.y_rel += y

        if z:
            t = abs(z) / abs(z_speed)
            if z < 0:
                z_speed = -abs(z_speed)

            await self.send_command("chassis speed z {}".format(z_speed))
            await asyncio.sleep(t)
            await self.send_command("chassis speed z 0")
            self.z_rel += z

    async def scan_square(self, distance):
        for i in range(6):
            await self.send_command("chassis attitude ?")
            await self.send_command("chassis position ?")



            await self.move(x=1.05 * distance, speed=0.2)
            await self.move(y=0.1 * distance, speed=0.1)

            await self.move(x=-1.05 * distance, speed=0.2)

            await self.move(y=0.1 * distance, speed=0.1)


            await self.send_command("chassis attitude ?")
            await self.send_command("chassis position ?")
            #await self._run_correction(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)

    async def _start(self, distance, pattern, record_gpr):
        " Main method for scanning square pattern"
        try:
            async with self.start_lock:


                await self.send_command("command")
                await self.send_command("chassis push freq 10")
                #await self.send_command("stream on")
                await self._get_position(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)

                #This is the full Scan of the square
                if pattern == "square":
                    # first scan
                    await self.scan_square(distance=distance)
                    # rotate 90 degrees and scan the perpandicular square
                    await self.move(x=0,y=0, z=-90, z_speed=30)
                    await self.scan_square(distance=distance)
                else:
                    await self.move(x=1.05 * distance, speed=0.1, record_gpr=record_gpr)
        except Exception as e:
            logger.exception("error in _start")
        finally:
            await self.send_command("quit")

    async def start(self, distance=1, pattern="square", record_gpr=False):
        print("called start with distance = {}".format(distance))
        if self.start_coro is not None:
            try:
                self.start_coro.cancel()
                await self.start_coro
            except Exception as e:
                logger.exception("failed to stop task")
        self.start_coro = asyncio.ensure_future(self._start(distance=distance, pattern=pattern,
                                                            record_gpr=record_gpr))


    async def cancel(self):
        self.z_rel, self.x_rel, self.y_rel = 0,0,0
        try:
            await self.send_command("quit")
            self.start_coro.cancel()
            await self.start_coro
        except Exception as e:
            logger.exception("failed to stop task")



if __name__ == '__main__':

    Move = RobotMove()

    asyncio.get_event_loop().run_until_complete(Move.main())
