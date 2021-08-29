# Plex Media Server Offline Downloader

PlexMedia-Downloader is a python script that you pass it your username, password, url to the media you have access to and it will download it to your local machine.

## Requirements

- Python 3
- Plex Server (With content you have access to stream from)
- Plex.TV account

## Python requirements

- requests
- tqdm

## Install

```
pip install requirements.txt
```

## Usage

URL can be any of the following ip:port, plex.direct:port, hostname:port, plex.tv

```
usage: main.py [-h] -u USERNAME -p PASSWORD url

positional arguments:
  url                   URL to Movie, Show, Season, Episode.

optional arguments:
optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        Plex.TV Email/Username
  -p PASSWORD, --password PASSWORD
                        Plex.TV Password
  -c COOKIE, --cookie COOKIE
                        Plex.tv Auth Sync cookie
  --original-filename   Name content by original name
  -t TOKEN, --token TOKEN
                        Plex Token
```

## Example

```
python main.py -u codedninja -p 3U7qYhaBAk8yfa 'https://app.plex.tv/desktop#!/server/0893cadc04a6f52efa052691d6a07c5b54890ca1/details?key=%2Flibrary%2Fmetadata%2F208649&context=source%3Ahub.tv.recentlyaired'
```
