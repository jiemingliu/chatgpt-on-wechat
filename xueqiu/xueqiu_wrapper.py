import argparse
from time import sleep

import schedule
import threading
from xueqiu import xueqiu
from common.log import logger

def start_loop_xueqiu():
    schedule_interval = 15
    schedule.every(schedule_interval).minutes.at(":15").do(xueqiu.main)# 比如09:15:15过了15秒启动正常不会调用两次循环函数
    xueqiu.logger.info('雪球循环间隔设置为%d分钟', schedule_interval)

    # xueqiu.main()  # 立即执行一次
    while True:
        try:
            schedule.run_pending()
            sleep(10)
        except KeyboardInterrupt:
            schedule.cancel_job(xueqiu.main)
            break

weiboThread = threading.Thread(target=start_loop_xueqiu)
weiboThread.setDaemon(True)
weiboThread.start()
