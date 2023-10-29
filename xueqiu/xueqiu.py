import argparse
import os 
import sys
import csv
import schedule
import threading
import requests
import json
import logging
import logging.config
from time import sleep
from selenium import webdriver
from bs4 import BeautifulSoup
from bridge.reply import ReplyType
from channel.wechat.wechat_channel import WechatMessage
from channel.wechat.wechat_channel import WechatChannel
from requests.adapters import HTTPAdapter
from io import BytesIO

if not os.path.isdir("log/"):
    os.makedirs("log/")
logging_path = os.path.split(os.path.realpath(__file__))[0] + os.sep + "logging.conf"
logging.config.fileConfig(logging_path)
logger = logging.getLogger("xueqiu")

def send_out_message(msg):
    WechatChannel().handle_weibo_msg(msg)
    return None

class Xueqiu(object):
    def __init__(self) -> None:
        self.csv_headers = ["id","正文"]
        self.users = ['9220236682']
        self.headers = {
            "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
        }
    def write_csv(self, headers, result_data, file_path):
        """将指定信息写入csv文件"""
        if not os.path.isfile(file_path):
            is_first_write = 1
        else:
            is_first_write = 0
        existContents = []
        if not is_first_write:
            file = open(file_path,'r', encoding="utf-8-sig")
            existContents = list(csv.reader(file))
            file.close
        existIds = []
        for content in existContents:
            existIds.append(list(content)[0])
        with open(file_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if is_first_write:
                writer.writerows([headers])
            for data in result_data:
                if data['id'] not in existIds:
                    msg = {}
                    msg['Content'] = data['contents']
                    msg['replytype'] = ReplyType.TEXT
                    send_out_message(msg)
                    if 'pic' in data:
                        for pic_path in data['pic']:
                            if not os.path.exists(pic_path) or not os.path.isfile(pic_path):
                                continue
                            msg['replytype'] = ReplyType.IMAGE
                            file = open(pic_path, "rb")
                            bytes_io = BytesIO(file.read())
                            file.close()
                            msg['Content'] = bytes_io
                            send_out_message(msg)
                    datas = []
                    datas.append(data['id'])
                    datas.append(data['contents'])
                    writer.writerow(datas)

    def download_one_file(self, url, file_path):
        """下载单个文件(图片/视频)"""
        try:
            file_exist = os.path.isfile(file_path)
            need_download = (not file_exist)
            if not need_download:
                return 

            s = requests.Session()
            s.mount(url, HTTPAdapter(max_retries=5))
            try_count = 0
            success = False
            MAX_TRY_COUNT = 3
            while try_count < MAX_TRY_COUNT:
                downloaded = s.get(
                    url, headers=self.headers, timeout=(5, 10), verify=False
                )
                try_count += 1
                fail_flg_1 = url.endswith(("jpg", "jpeg")) and not downloaded.content.endswith(b"\xff\xd9")
                fail_flg_2 = url.endswith("png") and not downloaded.content.endswith(b"\xaeB`\x82")

                if ( fail_flg_1  or fail_flg_2):
                    logger.debug("[DEBUG] failed " + url + "  " + str(try_count))
                else:
                    success = True
                    logger.debug("[DEBUG] success " + url + "  " + str(try_count))
                    break

            if success: 
                # 需要分别判断是否需要下载
                if not file_exist:
                    with open(file_path, "wb") as f:
                        f.write(downloaded.content)
                        logger.debug("[DEBUG] save " + file_path )
            else:
                logger.debug("[DEBUG] failed " + url + " TOTALLY")
        except Exception as e:
            logger.exception(e)

    def handle_download(self,urls:str,file_dir:str):
        ret = []
        if "," in urls:
            url_list = urls.split(",")
            for i, url in enumerate(url_list):
                u = url.replace('!thumb.jpg','')
                name_index = u.rfind('/')
                file_name = u[name_index+1:]
                file_path = file_dir + os.sep + file_name
                self.download_one_file(u, file_path)
                ret.append(file_path)
        else:
            urls = urls.replace('!thumb.jpg','')
            name_index = urls.rfind('/')
            file_name = urls[name_index+1:]
            file_path = file_dir + os.sep + file_name
            self.download_one_file(urls, file_path)
            ret.append(file_path)
        return ret

    def get_userinfo_from_xueqiu(self,id:str,pic_dir:str) -> None:
        # browser = webdriver.Chrome()
        # browser.get('https://xueqiu.com/u/9220236682')
        # for cookie in browser.get_cookies():
        #     if cookie['name'] == 'xq_a_token':
        #         header['Cookie'] = cookie['name'] + '=' + cookie['value']
        #         break
        url = 'https://xueqiu.com/snowman/provider/geetest?t=1695201053954&type=login_pwd'
        response = requests.get(url,headers=self.headers,verify=False)
        cookies = response.cookies
        cookies = requests.utils.dict_from_cookiejar(cookies)
        if 'xq_a_token'in cookies.keys():
            self.headers['Cookie'] = 'xq_a_token=' + cookies['xq_a_token']
        url = 'https://xueqiu.com/v4/statuses/user_timeline.json?page=1&user_id=' + id
        response = requests.get(url,headers=self.headers,verify=False)
        res = json.loads(response.text)
        result = []
        name = str
        for line in res['statuses']:
            ret = {}
            ret["id"] = str(line['id'])
            name = line['user']['screen_name']
            content = line['user']['screen_name'] + ':\n\n'
            content += BeautifulSoup(line['text'],'html.parser').get_text()
            if line['retweeted_status'] is not None:
                content += '\n\n@' + line['retweeted_status']['user']['screen_name'] + ':'
                bs4 = BeautifulSoup(line['retweeted_status']['text'],'html.parser')
                content += bs4.get_text().replace('网页链接','')
                links = bs4.find_all("a",attrs={"class":"status-link"})
                for link in links:
                    content += ' ' + link.get('href')
            ret['contents'] = str(content).replace('\n','')
            if line['pic']:
                ret['pic'] = self.handle_download(line['pic'],pic_dir)
            result.append(ret)
        logger.info("爬取雪球用户："+name+":"+str(result))
        return result

    def monitor_xueqiu_user(self):
        logger.info("开始爬取雪球用户")
        for user in self.users:
            file_dir = os.path.join(os.path.dirname(__file__),'data')
            file_dir = os.path.join(file_dir,user)
            if not os.path.isdir(file_dir):
                os.makedirs(file_dir)
            pic_dir = os.path.join(file_dir,'pic')
            if not os.path.isdir(pic_dir):
                os.makedirs(pic_dir)
            file_path = os.path.join(file_dir,user+".csv")
            self.write_csv(self.csv_headers,self.get_userinfo_from_xueqiu(user,pic_dir),file_path)


    def start(self):
        self.monitor_xueqiu_user()

def main():
    try:
        logger.info("循环一次爬取雪球用户"+str(threading.current_thread()))
        xueqiu = Xueqiu()
        xueqiu.start()
    except Exception as e:
        logger.error(e)