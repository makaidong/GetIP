#!/usr/bin/env python
# coding=utf8

# version:3.0
# kali linux python 2.7.13
# author:TClion
# update:2017-10-05
# 在西刺网站高匿网页上寻找可用ip并筛选出响应快的ip存放在ip.txt或mongodb中

import redis
import gevent
import logging
import pymongo
import requests

from lxml import etree
from gevent import monkey
from gevent import pool as gp
monkey.patch_all()

header = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'zh-CN,zh;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Host': 'www.xicidaili.com',
    'If-None-Match': '',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'

}  # xici代理的header头


class GetIp():
    def __init__(self):
        self.Url = "http://www.xicidaili.com/nn/"  # xici代理页面
        self.testurl = 'http://ip.chinaz.com/getip.aspx'  # 测试页面
        self.R = redis.Redis(host='localhost', port=6379)
        self.conn = pymongo.MongoClient('localhost', 27017)
        self.m_db = self.conn['ipdb']
        self.m_coll = self.m_db['ip_good']
        self.redis_db = 'ip'
        self.new_ip_num = 0     # 新入库的ip数量
        self.fast_ip_num = 0    # 筛选后的ip数量
        self.fast_ip_lst = []   # 响应快ip的列表
        self.slow_num = 0       # 不符合标准的ip数量
        logging.basicConfig(level=logging.INFO)    #设置logging等级为DeBUG
        logging.getLogger("requests").setLevel(logging.WARNING)     #设置requests等级

    # 从西刺网站上抓取ip，全部放在redis中
    def GetIpDict(self, pagenumber):
        url = '%s%d' % (self.Url, pagenumber)
        content = requests.get(url, headers=header).content
        data = etree.HTML(content)
        ip = data.xpath('//tr[@class="odd"]/td[2]/text()|//tr[@class=""]/td[2]/text()')
        port = data.xpath('//tr[@class="odd"]/td[3]/text()|//tr[@class=""]/td[3]/text()')
        ip_list = list(zip(ip, port))
        for i, p in ip_list:
            try:
                ip_str = i + ':' + p
                self.R.sadd(self.redis_db, ip_str)
                self.new_ip_num += 1
            except:
                logging.error('new ip insert error')

    # 筛选出响应快的ip
    def GetFastIp(self, item):
        i = item.split(':')[0]
        p = item.split(':')[1]
        ip = 'http://' + i + ':' + p
        ip_dict = {
            'http': ip,
            'https': ip,
        }
        try:
            text = requests.get(self.testurl, proxies=ip_dict, timeout=5).text
            if i in text:
                logging.info(i + ' insert into fast list')
                self.fast_ip_lst.append({i: p})
                self.fast_ip_num += 1
            else:
                self.slow_num += 1
        except:
            self.slow_num += 1
        print self.slow_num

    # 将ip存入ip.txt中
    def SaveFastIp(self, fast_ip):
        with open('ip.txt', 'w') as f:  # 将优质ip写入文件
            for ip in fast_ip:
                f.write(str(ip) + '\n')

    # 从文件中读取ip列表
    def get_ip_lst(self):
        IpList = []
        with open('ip.txt', 'r') as f:
            lines = f.readlines()
        for ip in lines:
            ip_lst = ip.split('\'')
            i, p = ip_lst[1], ip_lst[3]
            ip_str = 'http://' + i + ':' + p
            ip_dict = {
                'http': ip_str,
                'https': ip_str,
            }
            IpList.append(ip_dict)
        return IpList


    #存入mongo，并记录数量，数量越高，ip越稳定
    def saveip_mongo(self):
        for item in self.fast_ip_lst:
            for i, p in item.iteritems():
                ip_str = i + ':' + p
                if self.m_coll.find_one({'ip':ip_str}) == None:
                    self.m_coll.insert({'ip': ip_str, 'num': 1})
                else:
                    self.m_coll.update({'ip': ip_str}, {"$inc": {"num": 1}})

    #将mongodb中的ip以num排序
    def goodip(self):
        ip_lst = self.m_coll.find().sort('num', pymongo.DESCENDING)
        for i in ip_lst:
            print i['ip'], i['num']

    #将num小于5的从库中删除
    def removeip(self):
        for i in xrange(1, 5):
            data = {'num': i}
            self.m_coll.remove(data)

    #从mongodb中返回ip列表
    def get_ip_lst_m(self):
        ip_lst = []
        for item in self.m_coll.find():
            ip_str = item['ip']
            ip = ip_str.split(':')[0]
            port = ip_str.split(':')[1]
            new_ip_str = 'http://' + ip + ':' + port
            ip_dict = {
                'http': new_ip_str,
                'https': new_ip_str,
            }
            ip_lst.append(ip_dict)
        return ip_lst

    #将好的ip存入ip.txt
    def save_good_ip(self):
        with open('ip.txt', 'w') as f:  # 将优质ip写入文件
            for ip in self.m_coll.find().sort('num', pymongo.DESCENDING):
                f.write(ip['ip'] + '\n')

if __name__ == '__main__':
    Ip = GetIp()
    thread = [gevent.spawn(Ip.GetIpDict, i) for i in xrange(1, 10)]
    gevent.joinall(thread)
    logging.info('new ip counts %d' % Ip.new_ip_num)

    # p = gp.Pool(5000)
    # p.map(Ip.GetFastIp, Ip.R.smembers(Ip.redis_db))
    # Ip.saveip_mongo()
    # print Ip.fast_ip_num
    # Ip.goodip()
    # Ip.SaveFastIp(Ip.fast_ip_lst) #存入ip.txt 中
    # print Ip.fast_ip_num

    # ip = Ip.get_ip_lst()  #取出并测试
    # Ip.removeip()
    # Ip.goodip()
    # ip_lst = Ip.get_ip_lst_m()
    # Ip.save_good_ip()

