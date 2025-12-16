from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Log
from textual import work
import asyncio

class SocketTui(App):
    """A TUI that listens on port 9000 and displays received data."""

    BINDINGS = [("q", "quit", "Quit")]
    CSS = """
    Log {
        border: solid green;
        height: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Log(id="log")
        yield Footer()

    async def on_mount(self) -> None:
        self.log_widget = self.query_one(Log)
        self.log_widget.write_line("Initializing server...")
        # Start server as a background task on the same loop
        asyncio.create_task(self.start_server())

    async def start_server(self):
        try:
            server = await asyncio.start_server(
                self.handle_client, '0.0.0.0', 9000
            )
            self.log_widget.write_line("Listening on 0.0.0.0:9000...")
            async with server:
                await server.serve_forever()
        except OSError as e:
            self.log_widget.write_line(f"Error starting server: {e}")

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        self.log_widget.write_line(f"Connection from {addr}")
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                message = data.decode('utf-8', errors='replace').strip()
                if message:
                     self.log_widget.write_line(f"{addr}: {message}")
        except Exception as e:
            self.log_widget.write_line(f"Error: {e}")
        finally:
            self.log_widget.write_line(f"Closed connection from {addr}")
            writer.close()
            await writer.wait_closed()

if __name__ == "__main__":
    app = SocketTui()
    app.run()