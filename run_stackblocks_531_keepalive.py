import asyncio
import sys

sys.path.insert(0, r"C:\Users\choi2\algeomath-skills")

import server  # noqa: E402


async def main() -> None:
    for command in ["clear", "stack 1 1 5", "stack 2 1 3", "stack 3 1 1"]:
        print(f"RUN {command}", flush=True)
        print(await server.stackblocks(command), flush=True)
    print("KEEPALIVE_ALGEOMATH_531", flush=True)
    await asyncio.Event().wait()


asyncio.run(main())
