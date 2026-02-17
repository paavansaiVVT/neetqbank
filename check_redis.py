from redis import Redis
r = Redis(decode_responses=True)
print(f"Queue qbank_v2_jobs length: {r.llen('qbank_v2_jobs')}")
print(f"Queue content (peek): {r.lrange('qbank_v2_jobs', 0, 5)}")
print(f"All keys: {r.keys('*')}")
