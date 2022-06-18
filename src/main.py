from aiohttp import web, ClientSession, ClientTimeout
from prometheus_async import aio
from prometheus_client import Gauge
import asyncio
import aiojobs
import random
import logging
import os
import pprint 
import yaml
import sys

# Read environment variables
CONFIG_FILE = os.environ.get("CONFIG_FILE", 'conf/config.yml') 

routes = web.RouteTableDef()
# Prometheus metrics
web_health_check = Gauge('web_health_check', 'Web health check', ['url','name'])

# needed to avoid metric duplication (old health check status for the same url)
web_health_check_cur = {}

def set_logging(log_file, log_format, log_to_stdout=False, level=logging.DEBUG):
    logging.basicConfig(filename=log_file, level=logging.DEBUG, format=log_format)
    log = logging.getLogger('')
    log.setLevel(level)
    format = logging.Formatter(log_format)
    # log to stdout
    if log_to_stdout:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(format)
        log.addHandler(ch)

@routes.get('/health')
async def hello(request):
    return web.Response(text='healthy')

async def scrape_job(app, check):
    health_check = web_health_check_cur.pop((check['url'], check['name']), None)
    if health_check:
        web_health_check.remove(check['name'], health_check)
    
    # by default check is FAILED
    metric_value = 0

    try:
        async with app["client-session"].get(check['url']) as resp:
            if resp.status == check['status'] if 'status' in check else 200:
                resp_body = await resp.text()
                if resp_body.strip() == check['response']:
                    logging.info(f"Check (name={check['name']} url={check['url']}) is OK")
                    metric_value = 1
                else:
                    logging.error(f"Check (name={check['name']} url={check['url']}) is FAILED. Wrong HTTP body: {resp_body}")
            else:
                logging.error(f"Check (name={check['name']} url={check['url']}) is FAILED. Wrong HTTP status code: {resp.status}")
    except Exception as e:
        logging.error(f"Check (name={check['name']} url={check['url']}), exception raised {type(e)}")
        web_health_check_cur[(check['name'], check['url'])] = 'NONE'

    web_health_check_cur[(check['name'], check['url'])] = metric_value
    web_health_check.labels(name=check['name'], url=check['url']).set(metric_value)

async def schedule_job(app, check):
    scheduler = await aiojobs.create_scheduler()
    while True:
        await scheduler.spawn(scrape_job(app=app, check=check))
        await asyncio.sleep(check['interval'] if 'interval' in check else config['interval'])

async def scrape(app):
    await asyncio.gather(*[schedule_job(app=app,check=check) for check in config['checks']])

async def start_background_tasks(app):
    timeout = ClientTimeout(total=config['timeout'])
    app["client-session"] = ClientSession(timeout=timeout)
    app['scrape'] = asyncio.create_task(scrape(app))

async def cleanup_background_tasks(app):
    app['scrape'].cancel()
    await app['scrape']
    await app["client-session"].close()

if __name__ == '__main__':
    try:
        with open(CONFIG_FILE, 'r') as ymlfile:
            config = yaml.load(ymlfile)
    except Exception as e:
        logging.fatal(f"can't open configuration file {CONFIG_FILE},  {e}\n")
        sys.exit(1)

    set_logging(log_file=config['log_file'], log_format=config['log_format'], log_to_stdout=True, level=config['level'])
    app = web.Application()
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    app.add_routes(routes)
    app.router.add_get('/metrics', aio.web.server_stats)
    web.run_app(app, port=config['port'], access_log_format='%a %t "%r" %s %b "%{Referer}i" "%{User-Agent}i" ')
