import asyncio
import logging
from error_handler import safe_handler

logging.basicConfig(level=logging.INFO)

@safe_handler
async def faulty_handler(update, context):
    print("Executing faulty handler...")
    result = 1 / 0
    return result

async def main():
    print("Testing safe_handler...")
    await faulty_handler(None, None)
    print("Test completed. The script didn't crash.")

if __name__ == "__main__":
    asyncio.run(main())
