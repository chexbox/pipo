from http.server import BaseHTTPRequestHandler, HTTPServer
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
        
        # filter path to prevent exposing my whole disk
        path = "./www" + ".".join(filter(lambda x: x != "", self.path.split(".")))
        if path[-1] == "/":
            path = path + "index.html"
        
        print(path)
        
        if os.path.exists(path):
            status = 200
            mime = mimetypes.guess_type(path)[0]
            with open(path, "rb") as f:
                content = f.read()
        
        self.send_response(status)
        self.send_header("Content-type", mime)
        if (len(content) > 5000 and mime.split("/")[0] in ["text", "application"]):
            content = self.gzipencode(content)
            self.send_header("Content-Encoding", "gzip")
        
        self.send_header("Content-length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        self.wfile.flush()

connections = []

async def broadcast(data):
    conn_i = 0
    while conn_i < len(connections):
        conn = connections[conn_i]
        
        if conn.closed:
            connections.pop(conn_i)
        else:
            await conn.send(data)
            conn_i += 1

async def handle_ws(websocket):
    await websocket.send("[SERVER]Connected.")
    print("new ws connection", websocket.remote_address)
    connections.append(websocket)
    
    while True:
        try:
            async for message in websocket:
                if (False):# check structure, moderation
                    await websocket.send("[SERVER]Could not be delivered.")
                else:
                    await broadcast(message)
        except websockets.exceptions.ConnectionClosedError:
            print("disconnected", websocket.remote_address)
            return
        
        # don't eat cpu time with the while loop
        time.sleep(0.001)      # causes a 1 ms response delay
            
async def main():
    async with websockets.server.serve(handle_ws, "", 8765):
        await asyncio.Future()  # run forever
        
def http_start():
    http_server = HTTPServer(("", 8080), MyServer)
    print("starting http")
    http_server.serve_forever()

if __name__ == "__main__":
    http_thread = Thread(target=http_start, args=[])
    http_thread.start()

    asyncio.run(main())
    