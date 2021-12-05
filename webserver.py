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
        distance = request.query.get('distance')
        pattern = request.query.get('pattern', "square")
        record_gpr = request.query.get('record_gpr', False)
        if not distance:
            distance = 1
        await self.robot.start(float(distance), pattern, record_gpr)
        data = self.robot.to_dict()
        return aiohttp.web.json_response(data)

    async def rest_video(self, request):

        await self.robot.send_command("command")
        await self.robot.send_command("stream off")
        await self.robot.send_command("stream on")
        return aiohttp.web.json_response({'success': True})

    async def rest_sprayer(self, request):
        seconds = request.query.get('time')
        if not seconds:
            seconds = 0.1
        await self.robot.run_sprayer(seconds=float(seconds))
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
            aiohttp.web.get('/video_on', self.rest_video),
            ])

        self.http_runner = aiohttp.web.AppRunner(self.http_app)

        await self.http_runner.setup()
        print("ran http setup")
        try:
            print("starting site...")
            self.http_site = aiohttp.web.TCPSite(self.http_runner,
                    self.http_address, self.http_port, reuse_address=True)
            await self.http_site.start()

            print("balh")
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


        # Setup exception handler

        def exception_handler(loop, context):
            logger.error("unhandled exception in %s: %s",
                context['future'] if 'future' in context else '<none>',
                context['message'],
                exc_info=context['exception']
                    if 'exception' in context else False)
            loop.stop()
        loop.set_exception_handler(exception_handler)

        return loop.run_until_complete(self.http_server())


server = RobotServer()
server.main()
