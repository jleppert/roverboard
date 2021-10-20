# -*- encoding: utf-8 -*-
# Test environment: Python 3.6

import socket
import sys
import asyncio
import os
from simple_pid import PID
import logging

logger = logging.getLogger(__name__)

# In direct connection mode, the default IP address of the robot is 192.168.2.1 and the control command port is port 40923.
host = os.environ.get("djihost", "127.0.0.1")


class RobotMove(object):
    # def __init__(self):
    #     address = (host, int(port))
    #
    #     self.ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #     self.ctrl_socket.connect(host, 40923)
    #
    #     push_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     self.event_socket.connect((self.robot_ip, 40925))
    robot_ip = "127.0.0.1"
    x = 0
    y = 0
    z = 0

    x_rel = 0
    y_rel = 0
    z_rel = 0

    def __init__(self):
        """ Each robot move class can only have one running start task"""
        self.start_lock = asyncio.Lock()
        self.start_coro = None


    def to_dict(self):
        data = {"x": self.x_rel, "y": self.y_rel, "z": self.z_rel,
                "is_running": self.start_lock.locked()}

        return data

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
        result = await read_socket.read(1024)
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


    async def move(self, x=0, y=0, speed = 0.2, z=0, z_speed=30):

        """ impliments move to relative position based on velocity and track position"""
        if x and y:
            logger.warning("unable to move with both X and Y")

        if x:
            t = abs(x) / abs(speed)
            if x < 0:
                speed = -abs(speed)
            await self.send_command("chassis speed x {}".format(speed))
            await asyncio.sleep(t)
            await self.send_command("chassis speed x 0 ")
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

    async def scan_square(self):
        for i in range(6):
            await self.send_command("chassis attitude ?")
            await self.send_command("chassis position ?")

            await self.move(x=1.05, speed=0.2)
            await self.move(y=0.1, speed=0.1)

            await self.move(x=-1.05, speed=0.2)

            await self.move(y=0.1, speed=0.1)


            await self.send_command("chassis attitude ?")
            await self.send_command("chassis position ?")
            #await self._run_correction(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)

    async def _start(self):
        " Main method for scanning square pattern"
        async with self.start_lock:

            await self.send_command("command")
            await self.send_command("chassis push freq 10")
            await self._get_position(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)


            # first scan
            await self.scan_square()
            # rotate 90 degrees and scan the perpandicular square
            await self.move(x=0,y=0, z=-90, z_speed=30)
            await self.scan_square()

    async def start(self):
        if self.start_coro is not None:
            try:
                self.start_coro.cancel()
                await self.start_coro
            except Exception as e:
                logger.exception("failed to stop task")
        self.start_coro = asyncio.ensure_future(self._start())


    async def cancel(self):
        self.z_rel, self.x_rel, self.y_rel = 0,0,0
        try:
            await self.send_command("quit")
            self.start_coro.cancel()
            await self.start_coro
        except Exception as e:
            logger.exception("failed to stop task")

    async def scan_square_legacy(self):
        for i in range(6):
            await self.send_command("chassis attitude ?")
            await self.send_command("chassis position ?")
            await self.send_command("chassis speed x 0.2")
            await asyncio.sleep(5.2)
            await self.send_command("chassis speed x 0")
            #await self._run_correction(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)

            await self.send_command("chassis speed y 0.1")
            await asyncio.sleep(1)
            await self.send_command("chassis speed y 0")
            await self.send_command("chassis speed x -0.2")
            await asyncio.sleep(5.2)
            await self.send_command("chassis speed x 0")
            await self.send_command("chassis speed y 0.1")
            await asyncio.sleep(1)
            await self.send_command("chassis speed y 0")
            await self.send_command("chassis attitude ?")
            await self.send_command("chassis position ?")
            #await self._run_correction(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)



    async def start_legacy(self):
        await self.connect()
        task = asyncio.ensure_future(self.read_events())
        #task = asyncio.ensure_future(self.read_position_loop())
        await self.send_command("command")
        await self.send_command("chassis push freq 10")
        await self._get_position(read_socket=self.ctrl_reader, write_socket=self.ctrl_writer)


        # first scan
        await self.scan_square_legacy()
        # rotate 90 degrees and scan the perpandicular square
        await self.send_command("chassis speed z -30")
        await asyncio.sleep(3)
        await self.send_command("chassis speed z 0")

        await self.scan_square_legacy()

    async def main(self):
        await self.connect()
        await self.start()


if __name__ == '__main__':

    Move = RobotMove()

    asyncio.get_event_loop().run_until_complete(Move.main())

# def main():
#
#         address = (host, int(port))
#         push_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#
#
#         # Establish a TCP connection with the control command port of the robot.
#         s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#
#         print("Connecting...")
#
#         s.connect(address)
#
#         print("Connected!")
#
#         while True:
#
#                 # Wait for the user to enter control commands.
#                 msg = input(">>> please input SDK cmd: ")
#
#                 # When the user enters Q or q, exit the current program.
#                 if msg.upper() == 'Q':
#                         break
#
#                 # Add the ending character.
#                 msg += ';'
#
#                 # Send control commands to the robot.
#                 s.send(msg.encode('utf-8'))
#
#                 try:
#                         # Wait for the robot to return the execution result.
#                         buf = s.recv(1024)
#
#                         print(buf.decode('utf-8'))
#                 except socket.error as e:
#                         print("Error receiving :", e)
#                         sys.exit(1)
#                 if not len(buf):
#                         break
#
#         # Disconnect the port connection.
#         s.shutdown(socket.SHUT_WR)
#         s.close()
#
# if __name__ == '__main__':
#         main()
