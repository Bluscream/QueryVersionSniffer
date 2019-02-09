#!/usr/bin/python3
from time import sleep
from requests import post, get, Session
from urllib import parse
from traceback import format_exc
import logging
# from csv import reader, DictReader
# from contextlib import closing
from json import loads
from re import compile, match, search
from codecs import register, lookup # , iterdecode
register(lambda name: lookup('utf-8') if name == 'cp65001' else None)
from ts3 import query, response
from telegram import Bot, ParseMode
from fritzconnection import FritzConnection
from config import *
logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(levelname)s\t| %(message)s') # \t|%(name)s
logger = logging.getLogger()

running = False
versions = list()
version_pattern = compile(r"3(?:\.\d+)* \[Build: \d+\]")
sign_pattern = compile(r"[A-z0-9\/\+]{86}==")
platforms = ["Windows","Linux","OS X","Android","iOS"]

class Version(object):
        valid_version = False
        version = None
        valid_platform = False
        platform = None
        valid_sign =False
        sign = None
        def __init__(self, version, platform, sign):
                version_match = search(version_pattern, version)
                if (version_match):  self.version = version_match.string; self.valid_version = True
                else: self.version = version
                self.platform = platform
                self.valid_platform = platform in platforms
                sign_match = search(sign_pattern, sign)
                if (sign_match): self.sign = sign_match.string; self.valid_sign = True
                else: self.sign = sign

def merge_no_duplicates(iterable_1, iterable_2):
    myset = set(iterable_1).union(set(iterable_2))
    return list(myset)

def getVersionsFromRemote():
        download = session.get(csv_url)
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

def submitVersion(version, uid=None):
        # version.version = parse.quote_plus(version.version)
        url = "https://splamy.de/api/teamspeak/version/{version}/{platform}".format(version=version.version, platform=version.platform)
        params = {"sign": version.sign}
        headers = { "Content-Type": "application/json" }
        if uid: headers["X-From-Client"] = uid
        r = session.post(url, params=params, data=bytearray(), headers=headers)
        print("\"",r.url,"\"")
        print(loads(r.text))

session = Session()
try:
        versions = getVersionsFromRemote()
        versions = merge_no_duplicates(versions, getVersionsFromLocal())
except: versions = getVersionsFromLocal()
versions = list(filter(None, versions))

# updater.start_polling()
# updater.idle()

# for version in versions: print(version)
running = True

# submitVersion(Version("0.0.1 [Build: 1549713549]", "Linux", "7XvKmrk7uid2ixHFeERGqcC8vupeQqDypLtw2lY9slDNPojEv//F47UaDLG+TmVk4r6S0TseIKefzBpiRtLDAQ=="), "SAJRnGpF2d4SAY2tbtf4JdDm2I4=")

while(running):
        tgbot = Bot(tg_token)
        fritzbox = FritzConnection(address=fritzbox_address,user=fritzbox_user,password=fritzbox_password)
        neednewip = False
        success = 0
        logger.info("Started sniffing {} servers".format(len(servers)))
        for server in servers:
                success_clients = 0
                try:
                        logger.info("Now sniffing on {}".format(server))
                        with query.TS3ServerConnection(server[0]) as ts3conn:
                                ts3conn.exec_("use", port=server[1])
                                clientlist = ts3conn.exec_("clientlist")
                                if (clientlist.error["id"]!= "0" or clientlist.error["msg"] != "ok"):
                                        logger.error("Unable to get clientlist: {}".format(clientlist.error))
                                        continue
                                for client in clientlist:
                                        try:
                                                if (client["client_type"] != "0"): continue
                                                logger.debug(client)
                                                # logger.debug("CLIENT clid: {} dbid: {} name: {} ")
                                                clientinfo = ts3conn.exec_("clientinfo", clid=client["clid"])
                                                if (clientinfo.error["id"] != "0" or clientinfo.error["msg"] != "ok"):
                                                        logger.error( "Unable to get clientinfo for client \"{}\" ({}): {}".format(client["client_nickname"], client["clid"], clientinfo.error))
                                                        continue
                                                clientinfo = clientinfo.parsed[0]
                                                # logger.info(clientinfo)
                                                version = Version(clientinfo["client_version"], clientinfo["client_platform"], clientinfo["client_version_sign"])
                                                # print("ver:",version.valid_version, "platform:",version.valid_platform, "sign:",version.valid_sign)
                                                version_str = ','.join([version.version,version.platform,version.sign])
                                                # print(version_str)
                                                success_clients += 1
                                                if version_str in versions: sleep(sleep_after_client); continue
                                                versions.append(version_str)
                                                with open(csv_path, "a") as f: f.write("\nStable,"+version_str)
                                                nick = client["client_nickname"];uid = clientinfo["client_unique_identifier"] # ;uid_encoded = parse.quote_plus(uid)
                                                msg_print = "New Version from \"{}\" (`{}`):".format(nick.encode('utf-8'), uid)
                                                msg_tg = "`{}` (`{}`):".format(nick, uid)
                                                logger.info(msg_print, version_str)
                                                tgbot.send_message(chat_id=tg_chatid, text=msg_tg + "\n```csv\n" + version_str + "\n```", parse_mode=ParseMode.MARKDOWN)
                                                submitVersion(version, uid)
                                                sleep(sleep_after_client_new_version)
                                        except query.TS3QueryError as err: logger.error(err.args[0]); continue
                                        except: logger.error(format_exc()); continue
                                logger.info("Successfully sniffed {}/{} clients".format(success_clients, len(clientlist)))
                                success += 1
                except query.TS3TransportError as err:
                        logger.warning("Connection blocked by firewall, changing IP and waiting 30s before next run...")
                        neednewip = True; continue
                except: logger.error(format_exc()); continue
        logger.info("Successfully sniffed {}/{} servers".format(success, len(servers)))
        if neednewip:
                fritzbox.reconnect()
                sleep(sleep_ipchange)
        else: sleep(sleep_after_run)