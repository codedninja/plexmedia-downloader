#!/usr/bin/env python3
import requests
from urllib.parse import urlparse, unquote, parse_qs
from xml.etree import ElementTree
from tqdm.auto import tqdm
import os

# Config
email=""
password=""

class PlexDownloader:
    headers = {
            'X-Plex-Client-Identifier': 'PlexDownloader',
            'X-Plex-Product': 'PlexDownloader',
            'Accept': 'application/json'
    }

    base_url = ""

    servers = {}

    def login(self):
        #login
        payload = {
            'user[login]': self.email,
            'user[password]': self.password
        }
        
        r = requests.post("https://plex.tv/users/sign_in.json", headers=self.headers, data=payload)

        self.user = r.json()['user']

        return self.user

    def get_servers(self):
        #get servers
        headers = {
            **self.headers,
            'X-Plex-Token': self.user['authToken']
        }

        r = requests.get("https://plex.tv/pms/servers.xml", headers=headers)
    
        tree = ElementTree.fromstring(r.text)

        for xml_server in tree.findall('Server'):
            server = {
                    'id': xml_server.attrib['machineIdentifier'],
                    'access_token': xml_server.attrib['accessToken'],
                    'name': xml_server.attrib['name'],
                    'address': xml_server.attrib['address'],
                    'port': xml_server.attrib['port']
            }

            self.servers[server['id']] = server
        return self.servers

    def _generate_baseurl(self):
        server = self.servers[self.server_hash]
        self.access_token = server['access_token']
        headers = {
            **self.headers,
            'X-Plex-Token': server['access_token']
        }
    

        host_port = server['address']+":"+server['port']
    
        try:
            # Try getting host name
            url = "https://"+host_port
            r = requests.get(url, headers=headers)

            self.base_url = url
            print("Found Plex.Direct URL %s" % self.base_url)
            
            return url
        except requests.exceptions.SSLError as e:
            string_error = str(e)

            if ".plex.direct" in string_error:
                subdomain = str(e).split("doesn't match")[1].lstrip("'* ").rstrip("'\")")
           
                ip = server['address'].replace('.', '-')

                url = "https://"+ip+subdomain+":"+server['port']

                r = requests.get(url, headers=headers)
            
                if r.status_code == 200:
                    self.base_url = url
                    print("Found Plex.Direct URL %s" % self.base_url)
                    return url
                else:
                    print("Couldn't find Direct.Plex url for Plex Media Server")
                    return False
            else:
                print("Custom cert is enabled, don't know what to do.")
                return False
    
    def _get_url(self, url):
        headers = {
            **self.headers,
            'X-Plex-Token': self.access_token
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return False

    def _parse_show(self, rating_key):
        url = self.base_url+"/library/metadata/"+rating_key+"/allLeaves"

        response = self._get_url(url)

        if response:
            return self._parse_episodes(response['MediaContainer']['Metadata']) 
        
        return False

    def _parse_episodes(self, episodes):
        parsed_episodes = []

        for episode in episodes:
            if episode['type'] == "episode":
                parsed_episode = self._parse_episode(episode)
                parsed_episodes.append(parsed_episode)
        
        return parsed_episodes

    def _parse_episode(self, episode):
        key = episode['Media'][0]['Part'][0]['key']
        extension = key.split(".")[-1]
        # Show - s01e01 - Episode Title
        season_number = str(str(episode['parentIndex']).zfill(2))
        episode_number = str(str(episode['index']).zfill(2))
        filename = episode['grandparentTitle']+" - s"+season_number+"e"+episode_number+" - "+episode['title']+"."+extension
        folder = os.path.join(episode['grandparentTitle'], episode['parentTitle'])

        return {
                "url": self.base_url+key,
                "filename": filename,
                "folder": folder,
                "title": episode['title']
        }

    def _parse_season(self, rating_key):
        url = self.base_url+"/library/metadata/"+rating_key+"/children"

        parsed_episodes = []

        response = self_get_url(url)

        if response:
            return self._parse_episodes(response['MediaContainer']['Metadata'])

        return False

    def _parse_movie(self, movie):
        key = movie["Media"][0]['Part'][0]['key']
        extension = key.split(".")[-1]
        filename = movie['title']+"."+extension
        folder = movie['title']
        title = movie['title']

        return [
            {
                "url": self.base_url+key,
                "filename": filename,
                "folder": folder,
                "title": movie['title']
            }
        ]

    def _parse_metadata(self, data):
        media_content = []

        for media in data:
            rating_key = media['ratingKey']
            if media['type'] == "show":
                parsed_media = self._parse_show(rating_key)

            elif media['type'] == "season":
                parsed_media = self._parse_season(rating_key)

            elif media['type'] == "episode":
                parsed_media = self._parse_episode(media)
                
            elif media['type'] == "movie":
                parsed_media = self._parse_movie(media)

            else:
                print("Media type %s isn't supported yet" % media['type'])
                continue
                
            media_content = media_content + parsed_media
        return media_content
   
    def _get_metadata(self):
        url = self.base_url+self.rating_key

        response = self._get_url(url)

        if response:
            return self._parse_metadata(response['MediaContainer']['Metadata'])
        
        return False

    def download(self):
        user = self.login()
        print("Logged in as: %s" % user['username'])

        servers = self.get_servers()
        server_count = len(servers)
        print("Found %s servers" % server_count)

        server = self.servers[self.server_hash]

        print("Looking for Plex.Direct URL to %s" % server['name'])
        self._generate_baseurl()

        print("Getting urls of content to download.")
        contents = self._get_metadata()

        if not contents:
            print("Couldn't get metadata")
            return

        print("Found %s media content to download" % len(contents))

        headers = {
            **self.headers,
            'X-Plex-Token': self.access_token
        }

        for content in contents:
            if not os.path.exists(content['folder']):
                print("Directories don't exists, creating folders")
                os.makedirs(content['folder'])
            
            file_name = os.path.join(content['folder'], content['filename'].replace("/", "-"))
           
            response = requests.get(content['url'], stream=True, headers=headers)

            with open(file_name, "wb") as fout:
                with tqdm(
                    unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                    desc=file_name, total=int(response.headers.get('content-length', 0))
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=4096):
                        fout.write(chunk)
                        pbar.update(len(chunk))
        return

    def parse_url(self, url):
        fragment = urlparse(url).fragment.strip('!').split('/')
        self.server_hash = fragment[2]
        self.rating_key = parse_qs(fragment[3].split('?')[1])['key'][0]

        return True

    def __init__(self, email, password):
        self.email = email
        self.password = password

plex = PlexDownloader(email, password)
plex.parse_url("")

plex.download()
