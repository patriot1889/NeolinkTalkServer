import asyncio
import websockets
import subprocess
import sys
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description='WebSocket server for Neolink audio communication')
    parser.add_argument('--port', type=int, default=8585,
                      help='Port to run the WebSocket server on')
    parser.add_argument('--neolink-cmd', type=str, default='./neolink',
                      help='Path to the neolink executable')
    parser.add_argument('--camera-name', type=str, default='Door',
                      help='Name of the camera to connect to')
    parser.add_argument('--neolink-config', type=str, default='neolink.toml',
                      help='Path to the neolink configuration file')
    parser.add_argument('--volume', type=float, default=1.0,
                      help='Audio volume (0.0-1.0)')
    return parser.parse_args()

def get_neolink_cmd(args):
    return [
        args.neolink_cmd,
        "talk",
        args.camera_name,
        "-c", args.neolink_config,
        f"--volume={args.volume}",
        "-m",
        "-i", "fdsrc fd=0"
    ]

async def handle_audio(websocket, neolink_cmd):
    print(f"Client connected: {websocket.remote_address}")

    process = subprocess.Popen(
        neolink_cmd,
        stdin=subprocess.PIPE,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    async def feed_audio():
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    process.stdin.write(message)
                    process.stdin.flush()
                else:
                    print("Received non-bytes message, ignoring.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass

    feed_task = asyncio.create_task(feed_audio())
    try:
        while True:
            if process.poll() is not None:
                print("Neolink process exited.")
                break
            if feed_task.done():
                print("WebSocket closed by client.")
                break
            await asyncio.sleep(0.1)
    finally:
        process.terminate()
        await websocket.close()

async def main():
    args = parse_arguments()
    neolink_cmd = get_neolink_cmd(args)
    
    async def wrapped_handle_audio(websocket):
        await handle_audio(websocket, neolink_cmd)
    
    async with websockets.serve(wrapped_handle_audio, "0.0.0.0", args.port, max_size=None, max_queue=None):
        print(f"WebSocket server listening on port {args.port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())