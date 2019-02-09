#!/usr/bin/python3
from time import sleep
from requests import Session, post # get
from urllib import parse
from traceback import format_exc
import logging
# from csv import reader, DictReader
# from contextlib import closing
from codecs import register, lookup # , iterdecode
register(lambda name: lookup('utf-8') if name == 'cp65001' else None)
from ts3 import query
from telegram import Bot, ParseMode
from fritzconnection import FritzConnection
from config import *
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)

running = False
versions = list()

class Version(object):
        version = None
        platform = None
        sign = None
        def __init__(self, version, platform, sign):
                self.version = version; self.platform = platform; self.sign = sign

def merge_no_duplicates(iterable_1, iterable_2):
    myset = set(iterable_1).union(set(iterable_2))
    return list(myset)

def getVersionsFromRemote():
        with Session() as s:
                download = s.get(csv_url)
                decoded_content = download.content.decode('utf-8')
                lines = decoded_content.splitlines()[1:]
                return map(lambda it: it.strip().partition(",")[2], lines)
        # noinspection PyUnreachableCode
        """
        with closing(get(csv_url, stream=True)) as r:
                return DictReader(iterdecode(r.iter_lines(), 'utf-8'), delimiter=',', fieldnames=['channel','version','platform','hash'])
        """

def getVersionsFromLocal():
        with open(csv_path) as f:
                lines = f.readlines()[1:]
                return map(lambda it: it.strip().partition(",")[2], lines)

def submitVersion(version):
        version_encoded = parse.quote_plus(version.version)
        url = "https://splamy.de/api/teamspeak/version/{version}/{platform}".format(version=version_encoded, platform=version.platform)
        params = {"sign": version.sign}
        r = post(url, params=params, data=bytearray())
        print(r.url, r.status_code, r.reason, r)

try:
        versions = getVersionsFromRemote()
        versions = merge_no_duplicates(versions, getVersionsFromLocal())
except: versions = getVersionsFromLocal()
versions = list(filter(None, versions))

# updater.start_polling()
# updater.idle()

# for version in versions: print(version)
running = True

while(running):
        tgbot = Bot(tg_token)
        fritzbox = FritzConnection(address=fritzbox_address,user=fritzbox_user,password=fritzbox_password)
        neednewip = False
        for server in servers:
                try:
                        with query.TS3ServerConnection(server[0]) as ts3conn:
                                ts3conn.exec_("use", port=server[1])
                                clientlist = ts3conn.exec_("clientlist")
                                for client in clientlist:
                                        try:
                                                if (client["client_type"] != "0"): continue
                                                clientinfo = ts3conn.query("clientinfo").params(clid=client["clid"]).first()
                                                version = Version(clientinfo["client_version"], clientinfo["client_platform"], clientinfo["client_version_sign"])
                                                version_str = ','.join([version.version,version.platform,version.sign])
                                                if version_str in versions: sleep(sleep_after_client); continue
                                                versions.append(version_str)
                                                with open(csv_path, "a") as f: f.write("\nStable,"+version_str)
                                                nick = client["client_nickname"].encode('utf-8');uid = clientinfo["client_unique_identifier"] # ;uid_encoded = parse.quote_plus(uid)
                                                msg_print = "New Version from \"{}\" (`{}`):".format(nick, uid)
                                                msg_tg = "`{}` (`{}`):".format(nick, uid)
                                                logger.info(msg_print, version_str)
                                                tgbot.send_message(chat_id=tg_chatid, text=msg_tg + "\n```csv\n" + version_str + "\n```", parse_mode=ParseMode.MARKDOWN)
                                                submitVersion(version)
                                                sleep(sleep_after_client_new_version)
                                        except: print(format_exc()); continue
                except query.TS3TransportError as err:
                        logger.warning("Connection blocked by firewall, changing IP and waiting 30s before next run...")
                        neednewip = True; continue
                except query.TS3QueryError as err: logger.error(err.args); continue
                except: logger.error(format_exc()); continue
        if neednewip:
                fritzbox.reconnect()
                sleep(sleep_ipchange)
        else: sleep(sleep_after_run)