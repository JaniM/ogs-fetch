# ogs-fetch
Fetches SGF records for players from OGS.

Requires Python 3.6+ and the `requests` library.

[![asciicast](https://asciinema.org/a/uAwo6uDZI4DYwf8kDXt30bnFa.svg)](https://asciinema.org/a/uAwo6uDZI4DYwf8kDXt30bnFa?autoplay=1)
## Usage

First, add the user(s) you care about to the index. The first time you build the index will take a long time.
``` sh
python ogs-fetch.py --add <user id 1> <user id 2> <...>
```

Then just fetch the newest games:

``` sh
# Fetch *all* games from followed users:
python ogs-fetch.py -f

# Fwtch last ten games from followed users:
python ogs-fetch.py -f -l 10
```
