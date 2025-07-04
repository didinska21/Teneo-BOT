import json
import asyncio
import websockets
from datetime import datetime
from python_socks.async_.asyncio import Proxy
from python_socks._errors import ProxyError, ProxyTimeoutError, ProxyConnectionError
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich import box
import time

console = Console()

class ProxyConnectionException(Exception):
    pass

class FarmingUI:
    def __init__(self):
        self.start_time = time.time()
        self.connection_log = []
        self.response_log = []
        self.max_log_lines = 30
        self.total_traffic = 0

    def get_uptime(self):
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    def add_connection_log(self, message, color="white"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_text = Text(f"• [{timestamp}] {message}", style=color)
        self.connection_log.append(log_text)
        if len(self.connection_log) > self.max_log_lines:
            self.connection_log.pop(0)

    def update_traffic(self, bytes_count):
        self.total_traffic += bytes_count

    def make_layout(self):
        """Membuat layout untuk tampilan UI di terminal"""
        layout = Layout()
        layout.split(
            Layout(Panel(Text(f"Uptime: {self.get_uptime()}", style="bold cyan"), box=box.ROUNDED), name="header"),
            Layout(Panel("\n".join([str(log) for log in self.connection_log]), title="Connection Log"), name="log"),
        )
        return layout

class AccountWorker:
    def __init__(self, account_data, ui):
        self.account_id = account_data['account_id']
        self.access_token = account_data['access_token']
        self.proxy = account_data.get('proxy', '')
        self.ws_url = f"wss://secure.ws.teneo.pro/websocket?accessToken={self.access_token}&version=v0.2"
        self.ui = ui

    async def connect(self):
        retries = 5
        while retries > 0:
            try:
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Connecting...", "cyan")
                return await websockets.connect(self.ws_url)
            except Exception as e:
                retries -= 1
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Connection error ({5-retries}/5): {str(e)}", "red")
                await asyncio.sleep(5)
        return None

    async def send_pings(self, websocket):
        while True:
            try:
                await websocket.send(json.dumps({"type": "PING"}))
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Ping", "light_gray")
                await asyncio.sleep(10)
            except Exception as e:
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Ping error: {str(e)}", "red")
                return

    async def listen_responses(self, websocket):
        while True:
            try:
                message = await websocket.recv()
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Response: {message[:100]}...", "green")
            except websockets.exceptions.ConnectionClosed as e:
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Connection closed (code: {e.code})", "yellow")
                return
            except Exception as e:
                self.ui.add_connection_log(f"[Acc. {self.account_id}] Error: {str(e)}", "red")
                return

async def process_account(account_data, ui):
    while True:
        worker = AccountWorker(account_data, ui)
        ws = await worker.connect()
        if ws:
            try:
                await asyncio.gather(
                    worker.send_pings(ws),
                    worker.listen_responses(ws)
                )
            except Exception:
                pass
            finally:
                await ws.close()
        ui.add_connection_log(f"[Acc. {account_data['account_id']}] Restarting connection in 5 seconds...", "yellow")
        await asyncio.sleep(5)
