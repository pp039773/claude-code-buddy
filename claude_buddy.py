#!/usr/bin/env python3
"""Claude Code Buddy - a terminal pet companion.

Inspired by the (unofficial, no-longer-available) /buddy April Fools concept:
your identifier + a fixed seed feed a Mulberry32 PRNG that deterministically
rolls the pet's species, rarity, looks and stats. Same identifier -> same pet.
"""
import argparse
import getpass
import json
import os
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

STATE_PATH = os.path.join(os.path.expanduser("~"), ".claude_buddy_state.json")
SEED_SALT = "friend-2026-401"

SPECIES = [
    ("龍", "🐉"), ("貓", "🐱"), ("鴨子", "🦆"), ("狐狸", "🦊"), ("水獺", "🦦"),
    ("貓頭鷹", "🦉"), ("刺蝟", "🦔"), ("章魚", "🐙"), ("獨角獸", "🦄"), ("熊貓", "🐼"),
    ("企鵝", "🐧"), ("蜥蜴", "🦎"), ("浣熊", "🦝"), ("水母", "🎐"), ("螃蟹", "🦀"),
    ("青蛙", "🐸"), ("松鼠", "🐿️"), ("蝙蝠", "🦇"),
]
RARITIES = [("Common", 0.60), ("Uncommon", 0.25), ("Rare", 0.10), ("Epic", 0.04), ("Legendary", 0.01)]
EYES = ["圓亮眼", "瞇瞇眼", "星星眼", "愛心眼", "睡意眼", "銳利眼"]
HATS = ["無", "小帽子", "皇冠", "蝴蝶結", "眼鏡", "耳機", "圍巾", "花環"]
STAT_NAMES = ["DEBUGGING", "PATIENCE", "CHAOS", "WISDOM", "SNARK"]

TALK_LINES = {
    "low": ["...你確定這段邏輯是對的嗎？", "我快撐不住了，先 commit 吧。", "休息一下啦，拜託。"],
    "mid": ["繼續加油，我陪你除錯。", "這個 bug 有點意思。", "喝口水吧，順便存個檔。"],
    "high": ["今天狀態不錯喔！", "這段 code 寫得挺漂亮的。", "再來一個 feature 吧！"],
}


def mulberry32(seed):
    state = seed & 0xFFFFFFFF

    def next_val():
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        a = state
        t = ((a ^ (a >> 15)) * (1 | a)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return next_val


def seed_from_identifier(identifier):
    h = 0
    for ch in identifier + SEED_SALT:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def pick_index(rng, n):
    return min(int(rng() * n), n - 1)


def pick_weighted(rng, choices_with_weights):
    r = rng()
    acc = 0.0
    for item, w in choices_with_weights:
        acc += w
        if r <= acc:
            return item
    return choices_with_weights[-1][0]


def generate_pet(identifier):
    rng = mulberry32(seed_from_identifier(identifier))
    species, emoji = SPECIES[pick_index(rng, len(SPECIES))]
    rarity = pick_weighted(rng, RARITIES)
    shiny = rng() < 0.01
    eyes = EYES[pick_index(rng, len(EYES))]
    hat = HATS[pick_index(rng, len(HATS))]

    stats = {}
    for name in STAT_NAMES:
        low = int(rng() * 40) + 10
        peak = low + int(rng() * 40) + 20
        stats[name] = {"low": low, "peak": min(peak, 99), "current": (low + peak) // 2}

    now = datetime.now().isoformat()
    return {
        "identifier": identifier,
        "species": species,
        "emoji": emoji,
        "rarity": rarity,
        "shiny": shiny,
        "eyes": eyes,
        "hat": hat,
        "stats": stats,
        "hunger": 80,
        "energy": 80,
        "happiness": 80,
        "born": now,
        "last_update": now,
    }


def load_or_create(identifier):
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            pet = json.load(f)
    else:
        pet = generate_pet(identifier)
        save(pet)
    apply_decay(pet)
    return pet


def save(pet):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(pet, f, ensure_ascii=False, indent=2)


def apply_decay(pet):
    last = datetime.fromisoformat(pet["last_update"])
    hours = max((datetime.now() - last).total_seconds() / 3600, 0)
    pet["hunger"] = clamp(pet["hunger"] - hours * 3)
    pet["energy"] = clamp(pet["energy"] - hours * 2)
    pet["happiness"] = clamp(pet["happiness"] - hours * 2)
    pet["last_update"] = datetime.now().isoformat()


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def bar(value, width=20):
    filled = int(value / 100 * width)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {int(value):3d}"


def mood_bucket(pet):
    avg = (pet["hunger"] + pet["energy"] + pet["happiness"]) / 3
    if avg < 35:
        return "low"
    if avg < 70:
        return "mid"
    return "high"


def print_status(pet):
    shiny_tag = " ✨SHINY✨" if pet["shiny"] else ""
    print(f"{pet['emoji']}  {pet['species']}{shiny_tag}  [{pet['rarity']}]")
    print(f"眼睛: {pet['eyes']}　帽子: {pet['hat']}")
    print(f"擁有者: {pet['identifier']}　誕生於: {pet['born'][:19]}")
    print()
    print(f"飢餓 Hunger    {bar(pet['hunger'])}")
    print(f"精力 Energy    {bar(pet['energy'])}")
    print(f"心情 Happiness {bar(pet['happiness'])}")
    print()
    for name in STAT_NAMES:
        s = pet["stats"][name]
        print(f"{name:<10} {bar(s['current'])}  (peak {s['peak']} / low {s['low']})")


def cmd_status(pet, _args):
    print_status(pet)


def cmd_feed(pet, _args):
    pet["hunger"] = clamp(pet["hunger"] + 25)
    pet["happiness"] = clamp(pet["happiness"] + 5)
    print(f"你餵了 {pet['species']} 一頓好料 {pet['emoji']}")
    print_status(pet)


def cmd_play(pet, _args):
    pet["happiness"] = clamp(pet["happiness"] + 20)
    pet["energy"] = clamp(pet["energy"] - 15)
    pet["hunger"] = clamp(pet["hunger"] - 5)
    print(f"你跟 {pet['species']} 玩了一下，牠很開心！{pet['emoji']}")
    print_status(pet)


def cmd_sleep(pet, _args):
    pet["energy"] = clamp(pet["energy"] + 40)
    print(f"{pet['species']} 打了個盹，精力恢復了一些。💤")
    print_status(pet)


def cmd_talk(pet, _args):
    import random
    bucket = mood_bucket(pet)
    print(f"{pet['emoji']} {random.choice(TALK_LINES[bucket])}")


def cmd_reset(pet, args):
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)
    new_pet = generate_pet(args.who)
    save(new_pet)
    print("已重新孵化一隻新的 buddy！")
    print_status(new_pet)


def main():
    parser = argparse.ArgumentParser(description="Claude Code Buddy - 終端寵物")
    parser.add_argument("--who", default=getpass.getuser(), help="用來決定性生成寵物的識別字串（預設為系統使用者名稱）")
    sub = parser.add_subparsers(dest="command")
    for name, fn in [("status", cmd_status), ("feed", cmd_feed), ("play", cmd_play),
                      ("sleep", cmd_sleep), ("talk", cmd_talk), ("reset", cmd_reset)]:
        p = sub.add_parser(name)
        p.set_defaults(func=fn)

    args = parser.parse_args()
    command = args.command or "status"
    func = args.func if hasattr(args, "func") else cmd_status

    if command == "reset":
        func(None, args)
        return

    pet = load_or_create(args.who)
    func(pet, args)
    save(pet)


if __name__ == "__main__":
    main()
