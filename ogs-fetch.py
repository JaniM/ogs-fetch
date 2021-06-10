import argparse
import dataclasses
import requests
import time
import json
from pathlib import Path
import os

def take(iterator, count):
    iterator = iter(iterator)
    if count is None:
        yield from iterator
    for _ in range(count):
        yield next(iterator)


def sanitize_name(name):
    return ''.join(c for c in name if c.isalnum() or c in (' ', '_'))

@dataclasses.dataclass
class Player:
    name: str
    rank: int

    @staticmethod
    def from_dict(dict):
        return Player(
            name=dict['name'],
            rank=dict['rank'],
        )

    @staticmethod
    def from_api_dict(dict):
        return Player(
            name=sanitize_name(dict['username']),
            rank=dict['ranking'],
        )

@dataclasses.dataclass
class GameInfo:
    id: int
    name: str
    white: Player
    black: Player

    @staticmethod
    def from_dict(dict):
        return GameInfo(
            id=dict['id'],
            name=sanitize_name(dict['name']),
            white=Player.from_dict(dict['white']),
            black=Player.from_dict(dict['black']),
        )

    @staticmethod
    def from_api_dict(dict):
        game = GameInfo(
            id=dict['id'],
            name=sanitize_name(dict['name']),
            white=Player.from_api_dict(dict['players']['white']),
            black=Player.from_api_dict(dict['players']['black']),
        )
        game.white.rank = dict['historical_ratings']['white']['ratings']['overall']['rating']
        game.black.rank = dict['historical_ratings']['black']['ratings']['overall']['rating']
        return game

def throttled_get(*args, throttle_delay=10, **kwargs):
    # TODO: Add throttling
    now = time.monotonic()
    diff = now - throttled_get.last_call
    if diff < 0.5:
        time.sleep(0.5 - diff)

    result = requests.get(*args, **kwargs)

    throttled_get.last_call = time.monotonic()

    if result.status_code == 429:
        # Rate limited,
        print(f'Got rate limited, sleeping for {throttle_delay}s...')
        time.sleep(throttle_delay)
        return throttled_get(*args, throttle_delay=throttle_delay*2, **kwargs)

    return result

throttled_get.last_call = 0.0

def list_user_games(user_id):
    # &source=play&ended__isnull=false&ordering=-ended
    query = {
        'page_size': '50',
        'source': 'play',
        'ended__isnull': 'false',
        'ordering': '-ended'
    }
    data = throttled_get(f"https://online-go.com/api/v1/players/{user_id}/games", params=query)
    data.raise_for_status()
    data = data.json()
    while True:
        for game in data['results']:
            yield GameInfo.from_api_dict(game)

        if data['next'] is None:
            break
        data = throttled_get(data['next']).json()

def read_index(user_id):
    path = f'./index/{user_id}.json'
    try:
        with open(path) as f:
            data = f.read()
            data = json.loads(data)
            old_games = [GameInfo.from_dict(item) for item in data]
    except IOError:
        old_games = []

    return old_games

def write_index(user_id, games):
    path = f'./index/{user_id}.json'
    data = json.dumps([dataclasses.asdict(game) for game in games])

    print(f'  Writing index to {path}')
    with open(path, 'w') as f:
        f.write(data)

def build_index(user_id):
    print(f'Building index for user {user_id}')
    Path('./index').mkdir(exist_ok=True)

    old_games = read_index(user_id)

    games = list_user_games(user_id)

    new_games = []
    for idx, game in enumerate(games):
        if old_games and old_games[0].id == game.id:
            print(f'  All caught up. {idx} games added.')
            break
        if idx % 50 == 0 and idx > 0:
            print(f'{idx}...')
        new_games.append(game)

    all_games = new_games + old_games
    if idx != 0:
        write_index(user_id, all_games)

    return all_games

def get_all_indices():
    files = [f for f in os.listdir('./index') if f.endswith('.json')]
    indices = {}
    for f in files:
        id = int(f[:-5])
        indices[id] = read_index(id)

    return indices

def load_game(user_id, game_info):
    # These values are already sanitized.
    game_name = f'{game_info.id} {game_info.name} [{game_info.black.name} vs {game_info.white.name}]'
    path = f'./games/{user_id}/{game_name}.sgf'
    if Path(path).exists():
        return

    data = throttled_get(f'http://online-go.com/api/v1/games/{game_info.id}/sgf/')
    data.raise_for_status()
    data = data.text

    try:
        with open(path, 'w') as f:
            f.write(data)
    except KeyboardInterrupt:
        Path(path).delete()
        raise

    print(f'  Saved game {path}')

def load_all_games(limit, added=None):
    indices = get_all_indices()
    for user_id in indices:
        if added and user_id in added:
            continue
        indices[user_id] = build_index(user_id)

    for user_id, games in indices.items():
        print(f'Loading games for user {user_id}')
        Path(f'./games/{user_id}').mkdir(parents=True, exist_ok=True)
        for game in take(games, limit):
            load_game(user_id, game)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--add', type=int, nargs='*')
    parser.add_argument('-l', '--limit', type=int)
    parser.add_argument('-f', '--fetch', action='store_true')
    args = parser.parse_args()

    if args.add is not None:
        for user_id in args.add:
            build_index(user_id)

    if args.fetch:
        load_all_games(limit=args.limit, added=args.add)
