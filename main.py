#!/usr/bin/env python3
import requests
from urllib.parse import urlparse, unquote, parse_qs
from tqdm.auto import tqdm
import os
import argparse
import base64
import json


class PlexDownloader:
    headers = {
        'X-Plex-Client-Identifier': 'PlexDownloader',
        'X-Plex-Product': 'PlexDownloader',
        'Accept': 'application/json'
    }

    servers = {}

    def login(self):
        if self.cookie is not None:
            cookie = str(base64.b64decode(self.cookie), "utf-8")
            self.token = json.loads(cookie)["token"]

        if self.token:
            # Get user info
            headers = {
                **self.headers,
                'X-Plex-Token': self.token
            }

            r = requests.get(
                "https://plex.tv/users/account.json", headers=headers)
        else:
            # Login
            payload = {
                'user[login]': self.email,
                'user[password]': self.password
            }

            r = requests.post("https://plex.tv/users/sign_in.json",
                              headers=self.headers, data=payload)

        if r.status_code != 201:
            print(r.json()["error"])
            quit(1)

        self.user = r.json()['user']

        return self.user

    def get_servers(self):
        # get servers
        headers = {
            **self.headers,
            'X-Plex-Token': self.user['authToken']
        }

        r = requests.get(
            "https://plex.tv/api/v2/resources?includeHttps=1&includeRelay=1", headers=headers)

        for resources in r.json():
            server = {
                "id": resources["clientIdentifier"],
                "access_token": resources["accessToken"],
                "name": resources["name"],
                "public_address": resources["publicAddress"],
            }

            for connection in resources["connections"]:
                if connection["address"] == server["public_address"]:
                    server["address"] = connection["uri"]

            self.servers[server['id']] = server
        return self.servers

    def _get_url(self, url):
        headers = {
            **self.headers,
            'X-Plex-Token': self.server["access_token"]
        }

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return False

    def _parse_show(self, rating_key):
        url = self.server['address'] + \
            "/library/metadata/"+rating_key+"/allLeaves"

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
        if self.original_filename:
            filename = episode['Media'][0]['Part'][0]["file"].split("/")[-1]
        else:
            season_number = str(str(episode['parentIndex']).zfill(2))
            episode_number = str(str(episode['index']).zfill(2))
            filename = episode['grandparentTitle']+" - s"+season_number + \
                "e"+episode_number+" - "+episode['title']+"."+extension

        folder = os.path.join(
            episode['grandparentTitle'], episode['parentTitle'])

        return {
            "url": self.server['address']+key,
            "filename": filename,
            "folder": folder,
            "title": episode['title']
        }

    def _parse_season(self, rating_key):
        url = self.server['address'] + \
            "/library/metadata/"+rating_key+"/children"

        parsed_episodes = []

        response = self._get_url(url)

        if response:
            return self._parse_episodes(response['MediaContainer']['Metadata'])

        return False

    def _parse_movie(self, movie):
        key = movie["Media"][0]['Part'][0]['key']
        extension = key.split(".")[-1]

        if self.original_filename:
            filename = movie['Media'][0]['Part'][0]["file"].split("/")[-1]
        else:
            filename = movie['title']+"."+extension

        folder = movie['title']
        title = movie['title']

        return [
            {
                "url": self.server['address']+key,
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
                parsed_media = [self._parse_episode(media)]

            elif media['type'] == "movie":
                parsed_media = self._parse_movie(media)

            else:
                print("Media type %s isn't supported yet" % media['type'])
                continue

            media_content = media_content + parsed_media
        return media_content

    def _get_metadata(self):
        url = self.server["address"]+self.rating_key

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

        self.server = self.servers[self.server_hash]

        print("Getting urls of content to download.")
        contents = self._get_metadata()

        if not contents:
            print("Couldn't get metadata")
            return

        print("Found %s media content to download" % len(contents))

        headers = {
            'X-Plex-Token': self.server["access_token"]
        }

        for content in contents:
            if not os.path.exists(content['folder']):
                print("Directories don't exists, creating folders")
                os.makedirs(content['folder'])

            file_name = os.path.join(
                content['folder'], content['filename'].replace("/", "-"))

            response = requests.get(
                content['url'], stream=True, headers=headers)

            if response.status_code == 400:
                print("Error getting %s" % content['title'])
                continue

            with open(file_name, "wb") as fout:
                with tqdm(
                    unit='B', unit_scale=True, unit_divisor=1024, miniters=1,
                    desc=file_name, total=int(
                        response.headers.get('content-length', 0))
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=4096):
                        fout.write(chunk)
                        pbar.update(len(chunk))
        return

    def parse_url(self, url):
        if not url:
            print("No url provided")
            return False

        fragment = urlparse(url).fragment.strip('!').split('/')
        self.server_hash = fragment[2]
        self.rating_key = parse_qs(fragment[3].split('?')[1])['key'][0]

        return True

    def command_line(self):
        ap = argparse.ArgumentParser()

        ap.add_argument("-u", "--username", required=False,
                        help="Plex.TV Email/Username")

        ap.add_argument("-p", "--password", required=False,
                        help="Plex.TV Password")

        ap.add_argument("-c", "--cookie", required=False,
                        help="Plex.tv Auth Sync cookie")

        ap.add_argument("--original-filename", required=False,
                        default=False, action='store_true', help="Name content by original name")

        ap.add_argument("-t", "--token", required=False, help="Plex Token")

        ap.add_argument(
            "url", help="URL to Movie, Show, Season, Episode. TIP: Put url inside single quotes.")

        args = ap.parse_args()

        self.email = args.username
        self.password = args.password
        self.token = args.token
        self.cookie = args.cookie
        self.original_filename = args.original_filename

        if ((self.email is None or self.password is None) and self.token is None and self.cookie is None):
            print("Username and psasword, token, or cookie is required")
            quit(1)

        self.parse_url(args.url)
        self.download()

    def __init__(self):
        return


if __name__ == "__main__":
    plex = PlexDownloader()
    plex.command_line()
