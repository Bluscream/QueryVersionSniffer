#!/usr/bin/python3
from time import sleep
from csv import reader, DictReader
from requests import Session, get
from contextlib import closing
from codecs import iterdecode
from ts3 import query

csv_path = "versions.csv"
csv_url = "https://raw.githubusercontent.com/ReSpeak/tsdeclarations/master/Versions.csv"
servers = [ "telnet://[2001:1608:10:247::248]:10011" ]

versions = list()

def getVersionsFromRemote():
        with Session() as s:
                download = s.get(csv_url)
                decoded_content = download.content.decode('utf-8')
                return DictReader(decoded_content.splitlines(), delimiter=',')
        # noinspection PyUnreachableCode
        """
                with closing(get(csv_url, stream=True)) as r:
                        return DictReader(iterdecode(r.iter_lines(), 'utf-8'), delimiter=',', fieldnames=['channel','version','platform','hash'])
                """

def getVersionsFromLocal():
        with open(csv_path) as f:
                lines = f.readlines() # iterdecode(f.readlines(), 'utf-8')
                return DictReader(lines, delimiter=',')

versions = getVersionsFromLocal()
for version in versions:
        print(version['version'])
exit(1337)

try: versions = getVersionsFromRemote()
except: versions = getVersionsFromLocal()

for server in servers:
        with query.TS3ServerConnection(server) as ts3conn:
                ts3conn.exec_("use", port=9987)
                self = ts3conn.query("whoami").fetch().parsed
                print(self)
                # exec_() returns a **TS3QueryResponse** instance with the response.
                clientlist = ts3conn.exec_("clientlist")
                print("Clients on the server:", len(clientlist.parsed))
                print("Error:", clientlist.error["id"], clientlist.error["msg"])

                # Note, the TS3Response class and therefore the TS3QueryResponse
                # class too, can work as a rudimentary container. So, these two
                # commands are equal:
                for client in clientlist:
                        print(client)
                        if (client["client_type"] != "0"): continue
                        clientinfo = ts3conn.query("clientinfo").params(clid=client["clid"]).first()
                        version = clientinfo["client_version"]
                        platform = clientinfo["client_platform"]
                        sign = clientinfo["client_version_sign"]
                        print(clientinfo["client_nickname"], version, platform, sign )
                        sleep(5)