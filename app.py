import asyncio
import os


async def handler(reader, writer):
    writer.close()
    await writer.wait_closed()


async def main():
    port = int(os.environ.get("PORT", 8080))

    server = await asyncio.start_server(
        handler,
        "0.0.0.0",
        port
    )

    print(f"Port server running on {port}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
