import argparse
from time import sleep

import schedule
import threading

import weibo.const as const
import weibo.weibo as weibo
from weibo.util.notify import push_deer


def start_loop_weibo():
    """
    主函数，用于设置定时任务和执行微博爬虫脚本。

    Parameters:
        schedule_interval (int): 循环间隔，以分钟为单位。

    Returns:
        None
    """
    schedule_interval = 1
    schedule.every(schedule_interval).minutes.do(weibo.main)  # 每隔指定的时间间隔执行一次main函数
    weibo.logger.info('循环间隔设置为%d分钟', schedule_interval)

    # weibo.main()  # 立即执行一次
    while True:
        try:
            schedule.run_pending()
            sleep(1)
        except KeyboardInterrupt:
            schedule.cancel_job(weibo.main)
            break
        except Exception as error:
            if const.NOTIFY["NOTIFY"]:
                push_deer(f"weibo-crawler运行出错, 错误为{error}")
                weibo.logger.exception(error)

weiboThread = threading.Thread(target=start_loop_weibo)
weiboThread.setDaemon(True)
weiboThread.start()
