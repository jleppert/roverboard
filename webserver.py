import aiohttp
import aiohttp.web
import logging
import asyncio
from move import RobotMove

logger = logging.getLogger(__name__)

class RobotServer(object):
    http_port = 9005
    http_address='0.0.0.0'

    async def setup(self):
        """ runs any on-startup initialization"""
        self.robot = RobotMove()
        await self.robot.connect()

    async def rest_start(self, request):
        print(request.query)
        await self.robot.start()
        data = self.robot.to_dict()
        return aiohttp.web.json_response(data)

    async def rest_sprayer(self, request):
        seconds = request.query.get('time', [None])[0]
        if not seconds:
            seconds = 0.1
        await self.robot.run_sprayer(seconds=seconds)
        return aiohttp.web.json_response({'success': True})

    async def rest_cancel(self, request):

        await self.robot.cancel()
        data = self.robot.to_dict()

        return aiohttp.web.json_response(data)

    async def rest_status(self, request):

        data = self.robot.to_dict()
        return aiohttp.web.json_response(data)

    async def http_server(self):
        self.http_app = aiohttp.web.Application()
        self.http_app.add_routes([
            aiohttp.web.get('/status', self.rest_status),
            aiohttp.web.get('/start', self.rest_start),
            aiohttp.web.get('/cancel', self.rest_cancel),
            aiohttp.web.get('/sprayer', self.rest_sprayer),
            ])

        self.http_runner = aiohttp.web.AppRunner(self.http_app)

        await self.http_runner.setup()
        print("ran http setup")
        try:
            self.http_site = aiohttp.web.TCPSite(self.http_runner,
                    self.http_address, self.http_port, reuse_address=True)
            await self.http_site.start()
            try:
                await self.setup()
            except Exception as e:
                logger.exception("unable to run setup")
            while True:
                await asyncio.sleep(10)
        finally:
            await self.http_runner.cleanup()

    def main(self):
        asyncio.set_event_loop(asyncio.new_event_loop())

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.http_server())


server = RobotServer()
server.main()
