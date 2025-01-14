import argparse
import asyncio
import logging
import os
from functools import partial

import aiofiles
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger('download-server')


async def archive(photo_dir: str, delay: int, request: web.Request) -> web.StreamResponse:
    archive_hash = request.match_info['archive_hash']
    path_to_photos = os.path.join(photo_dir, archive_hash)

    if not os.path.exists(path_to_photos):
        raise web.HTTPNotFound(reason='Archive does not exist or was removed.')

    response = web.StreamResponse(
        headers={
            'Content-Disposition': 'Attachment;filename=wedding_photos.zip',
        },
    )
    await response.prepare(request)

    process = await asyncio.create_subprocess_exec(
        "zip",
        "-r", "-", ".",
        cwd=path_to_photos,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    try:
        while not process.stdout.at_eof():
            data = await process.stdout.read(n=1024 * 100)

            logger.info(f'{archive_hash}: Sending archive chunk ...')
            await response.write(data)

            await asyncio.sleep(delay)

    except ConnectionResetError:
        logger.info(f'{archive_hash}: Download was interrupted')

    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()

    return response


async def handle_index_page(request: web.Request) -> web.Response:
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def get_app_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='AsyncDownloadService',
        description='Microservice for downloading zip photo archives,'
    )
    parser.add_argument('-p', '--path', help='path to photo storage dir')
    parser.add_argument(
        '-d', '--delay',
        type=int,
        choices=range(0, 61),
        help='time to wait before sending client next chunk of photo archive (0-60 sec)',
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='run microservice without log messages (default: false)',
    )

    return parser.parse_args()


def main():
    app_args = get_app_args()

    if app_args.quiet:
        logging.disable(logging.CRITICAL)

    delay = app_args.delay or 0
    photo_dir = app_args.path if app_args.path is not None else './test_photos'

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get(
            '/archive/{archive_hash}/',
            partial(archive, photo_dir, delay),
        ),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
