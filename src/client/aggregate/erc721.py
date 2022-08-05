# ERC721 Standard

import json
import asyncio
import aiohttp
import ssl
import certifi

from functools import cmp_to_key
import time
import os

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

weights = []
aggregate = {}
invalids = []
composed = []

proxies = ['socks5://192.111.129.145:16894',
           'socks5://67.201.33.10:25283',
           'socks5://98.162.25.23:4145']


async def count(token_uri, token_id, session, suffix, retry_limit):
    for attempt in range(retry_limit):  # Until I can get around rate limits >:(
        try:
            async with session.get("%s/%s%s" % (token_uri, token_id, suffix), ssl=SSL_CONTEXT) as response:
                res = await response.read()
                decoded_res = json.loads(res.decode("utf8"))

                attributes = decoded_res["attributes"]

                attributes.append({
                    'trait_type': 'num_traits',
                    'value': len([attrib for attrib in attributes if attrib['value']])
                })

                weights.append({
                    "token_id": token_id,
                    "attributes": attributes
                })

                for i in attributes:
                    if not i["trait_type"] in aggregate:
                        aggregate[i["trait_type"]] = {}

                    if not i["value"] in aggregate[i["trait_type"]]:
                        aggregate[i["trait_type"]][i["value"]] = {
                            "count": 0,
                            "weight": 0
                        }

                    aggregate[i["trait_type"]][i["value"]]["count"] += 1

                # print("✅:", token_id)
                return
        except Exception as e:
            # log
            continue

    # log
    invalids.append(token_id)
    print("❌:", token_id)


async def assign(attribute, limit):
    attribute["weight"] = round(1 / (attribute["count"] / limit), 3)


def weigh(metadata):
    if "weight" in metadata.keys():
        return metadata["weight"]

    weight = 0
    for attribute in metadata["attributes"]:
        weight += aggregate[attribute["trait_type"]
                            ][attribute["value"]]["weight"]

    metadata["weight"] = weight
    return weight


def compare(a, b):
    return weigh(a) - weigh(b)


async def main(project_name, token_uri, limit, starting_index=0, suffix="", retry_limit=500):
    start_time = time.time()
    async with aiohttp.ClientSession(trust_env=True) as session:
        token_uri = token_uri.replace(
            "ipfs://", "https://gateway.ipfs.io/ipfs/")
        print("--- COUNTING ---")
        await asyncio.gather(*[count(token_uri, num, session, suffix, retry_limit) for num in range(starting_index, starting_index + limit)])

        for attributes in aggregate.values():
            for attribute in attributes.values():
                composed.append(attribute)

        print("--- WEIGHING ---")
        await asyncio.gather(*[assign(attribute, limit) for attribute in composed])

        print("--- SORTING ---")
        weights.sort(key=cmp_to_key(compare), reverse=True)

        print("--- RANKING ---")
        current_rank, prev_weight = 1, weights[0]['weight']
        for weightIndex in range(len(weights)):
            if weights[weightIndex]['weight'] != prev_weight:
                prev_weight = weights[weightIndex]['weight']
                current_rank += 1

            weights[weightIndex]['rank'] = current_rank

    finalized_time = time.time() - start_time
    with open("%s.json" % (project_name.lower().replace(" ", "")), "w") as dumped:
        dumped.write(json.dumps({
            "project_name": project_name,
            "token_uri": token_uri,
            "limit": limit,
            "suffix": suffix,
            "starting_index": starting_index,
            "aggregate": aggregate,
            "weights": weights,
            "time_to_sync": finalized_time
        }))

    print("--- DONE ---")
    print("--- %s seconds ---" % (finalized_time))


def run(project_name, token_uri, limit, starting_index, suffix, retry_limit):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        main(project_name, token_uri, limit, starting_index, suffix, retry_limit))
    loop.close()


run("Otherdeeds for Otherside",
    "https://api.otherside.xyz/lands",
    # "ipfs://QmZEHrvfQyBDGYt6cdBn5cTC4VndCA9mGWGz9Z3pJokG7U",
    # "https://gateway.ipfs.io/ipfs/QmbKMjG6AZvLuNr7NynifQBknPPmoJiBqb1RszwdZmDtbb",
    limit=10,
    starting_index=0,
    suffix='',
    retry_limit=100)

print("INVALIDS:", invalids)
