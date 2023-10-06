from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer, HTTPServer
from threading import Thread

import mimetypes
import os

from io import BytesIO
import gzip

import asyncio
import websockets.server
import time

class MyServer(BaseHTTPRequestHandler):
    def gzipencode(self, content):
        out = BytesIO()
        f = gzip.GzipFile(fileobj=out, mode='w', compresslevel=5)
        f.write(content)
        f.close()
        return out.getvalue()

    def do_GET(self):
        status = 404
        mime = "text/plain"
        content = bytes("404 this page no exist", "utf-8")
        gzip = False
        
        # filter path to prevent exposing my whole disk
        path = "./www" + ".".join(filter(lambda x: x != "", self.path.split(".")))
        if path[-1] == "/":
            path = path + "index.html"
        
        # file in cache?
        if (path in file_cache and time.time() - file_cache[path]["time"] < 60.0):
            print("cached:", path)
            status = file_cache[path]["status"]
            mime = file_cache[path]["mime"]
            content = file_cache[path]["content"]
            gzip = file_cache[path]["gzip"]
        else: # load file
            print(path)
            
            if os.path.exists(path):
                status = 200
                mime = mimetypes.guess_type(path)[0]
                with open(path, "rb") as f:
                    content = f.read()
                    
            # use gzip?
            if (len(content) > 5000 and mime.split("/")[0] in ["text", "application"]):
                content = self.gzipencode(content)
                gzip = True
                
                # save to cache
            file_cache[path] = { "time": time.time(), "status": status, "mime": mime, "content": content, "gzip": gzip }
        
        self.send_response(status)
        self.send_header("Content-type", mime)
        if gzip:
            self.send_header("Content-Encoding", "gzip")
        
        self.send_header("Content-length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        self.wfile.flush()

channels = {}

async def broadcast(data, channel):
    conn_i = 0
    while conn_i < len(channels[channel]):
        conn = channels[channel][conn_i]
        
        if conn.closed:
            channels[channel].pop(conn_i)
        else:
            await conn.send(data)
            conn_i += 1
            
    if len(channels[channel]) == 0:
        del channels[channel]

async def handle_ws(websocket):
    print("new ws connection", websocket.remote_address)
    
    await websocket.send("[SERVER]Connected.")
    
    while True:
        try:
            # handle all new messages for this connection
            async for message in websocket:
                if ("]" in message and "[" in message.split("]")[0]):
                    channel = message.split("[")[0]
                    if (not channel in channels):
                        channels[channel] = [websocket]
                    elif (not websocket in channels[channel]):
                        channels[channel].append(websocket)
                    
                    await broadcast(message, channel)
                else:
                    await websocket.send("[SERVER]Could not be delivered.")
                    
        except (websockets.exceptions.ConnectionClosedError, ConnectionAbortedError) as e:
            print("disconnected", websocket.remote_address, e)
            return
        
        # don't eat cpu time with the while loop
        time.sleep(0.001)      # causes a 1 ms response delay
            
async def main():
    async with websockets.server.serve(handle_ws, "", 8765):
        await asyncio.Future()  # run forever
        
def http_start():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    http_server = ThreadingHTTPServer(("", 8080), MyServer)
    print("starting http")
    http_server.serve_forever()

if __name__ == "__main__":
    file_cache = {}
    http_thread = Thread(target=http_start, args=[])
    http_thread.start()

    asyncio.run(main())
    