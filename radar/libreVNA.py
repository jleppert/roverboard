import socket
import logging
from asyncio import IncompleteReadError  # only import the exception class
import asyncio

logger = logging.getLogger(__name__)


class AsyncTCP(object):
    def __init__(self, host='localhost', port=19542):
        self.host = host
        self.port = port

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        except:
            logger.exception("Failed to connect")
            raise Exception("Unable to connect to LibreVNA-GUI. Make sure it is running and the TCP server is enabled.")

    async def close(self):
        await self.writer.drain()
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except:
            print("python doesn't support wait_Closed, sleeping")
            await asyncio.sleep(0.1)


    async def read_response(self):
        data = await self.reader.readline()
        return data.decode().rstrip()

class RAWVNA(AsyncTCP):

    async def read_trace(self):
        ret = []
        data = await self.read_response()
        samples = data.split(';')

        for s in samples:
            freq, real, imag = s.split(',')
            ret.append(freq,complex(real,imag))
        return ret


class libreVNA(AsyncTCP):


    async def cmd(self, cmd):
        self.writer.write(cmd.encode() + b"\n")
        await self.writer.drain()
        return await self.read_response()

    async def query(self, query):
        self.writer.write(query.encode() + b"\n")
        await self.writer.drain()
        return await self.read_response()

    @staticmethod
    def parse_trace_data(data):
        ret = []
        # Remove brackets (order of data implicitly known)
        data = data.replace(']','').replace('[','')
        values = data.split(',')
        if int(len(values) / 3) * 3 != len(values):
            # number of values must be a multiple of three (frequency, real, imaginary)
            raise Exception("Invalid input data: expected tuples of three values each")
        for i in range(0, len(values), 3):
            freq = float(values[i])
            real = float(values[i+1])
            imag = float(values[i+2])
            ret.append((freq, complex(real, imag)))
        return ret
