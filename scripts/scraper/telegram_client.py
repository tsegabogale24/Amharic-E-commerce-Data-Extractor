import os
import csv
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import GetHistoryRequest

# Load environment variables
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")
PHONE = os.getenv("PHONE_NUMBER")

CHANNEL_USERNAMES = [
    '@AwasMart',
    '@classybrands',
    '@helloomarketethiopia',
    '@nevacomputer',
    '@sinayelj'
]

# Data directory structure
DATA_DIR = ROOT_DIR / "data" / "raw"
MEDIA_DIR = DATA_DIR / "media"  # For all media types
os.makedirs(MEDIA_DIR, exist_ok=True)

CSV_FILE = DATA_DIR / "telegram_messages.csv"

# Initialize CSV if needed
if not CSV_FILE.exists():
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow([
            'channel', 
            'sender_id', 
            'timestamp', 
            'message', 
            'views', 
            'media_path',
            'message_id',
            'message_type'
        ])

# Initialize Telegram client
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    connection_retries=3,
    request_retries=2,
    timeout=20,
    auto_reconnect=True
)

async def ensure_authentication():
    """Ensure we have a valid authenticated session"""
    try:
        if not client.is_connected():
            await client.connect()

        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"✅ Session valid for: {me.phone}")
            return True

        print("🔑 Starting authentication...")
        await client.start(phone=PHONE)

        if await client.is_user_authorized():
            print("✅ Authentication successful!")
            return True
        print("❌ Authentication failed")
        return False

    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        return False

class ChannelFetcher:
    def __init__(self):
        self.processed_messages = 0
        self.start_time = datetime.now(timezone.utc)
        self.failed_channels = []

    async def log_progress(self, username, count):
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        rate = count / elapsed if elapsed > 0 else 0
        print(f"\r📊 {username}: {count} messages | "
              f"{elapsed:.1f}s elapsed | "
              f"{rate:.1f} msg/s", end="", flush=True)

    async def save_batch(self, batch):
        """Save messages in batches to reduce I/O"""
        with open(CSV_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerows(batch)

    def get_message_content(self, msg):
        """Extract all text content from a message including captions"""
        # Basic message text
        text_content = msg.text or ""
        
        # Handle different message types
        if msg.media:
            # Get caption for media messages
            if hasattr(msg, 'message') and msg.message:
                text_content = msg.message
            elif hasattr(msg, 'caption') and msg.caption:
                text_content = msg.caption
            elif hasattr(msg.media, 'caption') and msg.media.caption:
                text_content = msg.media.caption
        
        # Clean and normalize the text
        text_content = ' '.join(text_content.split())  # Remove extra whitespace
        return text_content

    def get_message_type(self, msg):
        """Determine the type of message"""
        if not msg.media:
            return "text"
        
        if hasattr(msg.media, 'photo'):
            return "photo"
        elif hasattr(msg.media, 'document'):
            mime_type = getattr(msg.media.document, 'mime_type', '')
            if 'video' in mime_type:
                return "video"
            elif 'audio' in mime_type:
                return "audio"
            elif 'image' in mime_type:
                return "image"
            return "document"
        elif hasattr(msg.media, 'webpage'):
            return "webpage"
        return "media"

    async def fetch_channel(self, username, limit=100, days=30, download_media=True):
        """Fetch messages from a single channel"""
        try:
            print(f"\n🔍 Starting {username}...")
            try:
                entity = await asyncio.wait_for(client.get_entity(username), timeout=10)
            except asyncio.TimeoutError:
                print(f"⌛ Timeout getting entity for {username}")
                self.failed_channels.append(username)
                return 0

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            offset_id = 0
            offset_date = None
            message_count = 0
            batch = []

            while True:
                try:
                    messages = await asyncio.wait_for(
                        client(GetHistoryRequest(
                            peer=entity,
                            limit=limit,
                            offset_date=offset_date,
                            offset_id=offset_id,
                            max_id=0,
                            min_id=0,
                            add_offset=0,
                            hash=0
                        )),
                        timeout=30
                    )

                    if not messages.messages:
                        break

                    offset_date = messages.messages[-1].date

                    for msg in messages.messages:
                        if msg.date.replace(tzinfo=timezone.utc) < cutoff_date:
                            continue

                        # Get message content and type
                        message_content = self.get_message_content(msg)
                        message_type = self.get_message_type(msg)

                        media_path = ""
                        if msg.media and download_media:
                            try:
                                # Generate appropriate filename
                                if message_type == "photo":
                                    extension = "jpg"
                                    filename = f"{username[1:]}_{msg.id}.{extension}"
                                elif message_type in ["video", "audio", "document", "image"]:
                                    # Try to get original filename
                                    filename_attr = None
                                    for attr in msg.media.document.attributes:
                                        if hasattr(attr, 'file_name'):
                                            filename_attr = attr.file_name
                                            break
                                    if filename_attr:
                                        filename = f"{username[1:]}_{msg.id}_{filename_attr}"
                                    else:
                                        mime_type = msg.media.document.mime_type
                                        extension = mime_type.split('/')[-1] if mime_type else 'bin'
                                        filename = f"{username[1:]}_{msg.id}.{extension}"
                                else:
                                    filename = f"{username[1:]}_{msg.id}.bin"

                                full_path = MEDIA_DIR / filename
                                await asyncio.wait_for(
                                    msg.download_media(file=full_path),
                                    timeout=20
                                )
                                media_path = str(Path("media") / filename)
                            except Exception as e:
                                media_path = f"Error: {str(e)}"

                        batch.append([
                            username,
                            msg.sender_id,
                            msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                            message_content,  # Using the extracted content
                            getattr(msg, 'views', None),
                            media_path,
                            msg.id,
                            message_type  # Added message type
                        ])
                        message_count += 1
                        self.processed_messages += 1

                    await self.log_progress(username, message_count)

                    if len(batch) >= 20:
                        await self.save_batch(batch)
                        batch = []

                    offset_id = messages.messages[-1].id
                    if len(messages.messages) < limit:
                        break

                except errors.FloodWaitError as e:
                    print(f"\n⚠️ Flood wait for {e.seconds} seconds")
                    await asyncio.sleep(e.seconds)
                    continue
                except asyncio.TimeoutError:
                    print("\n⌛ Timeout, continuing...")
                    continue
                except Exception as e:
                    print(f"\n⚠️ Error: {str(e)}")
                    break

            if batch:
                await self.save_batch(batch)

            print(f"\n✅ Finished {username}: {message_count} messages")
            return message_count

        except Exception as e:
            print(f"\n❌ Failed {username}: {str(e)}")
            self.failed_channels.append(username)
            return 0

async def main():
    print("🚀 Starting Telegram scraper")
    print(f"📅 Loading data for {len(CHANNEL_USERNAMES)} channels")

    if not await ensure_authentication():
        print("🛑 Stopping script due to authentication issues")
        await client.disconnect()
        return

    fetcher = ChannelFetcher()

    async with client:
        total_messages = 0
        for username in CHANNEL_USERNAMES:
            count = await fetcher.fetch_channel(
                username,
                limit=100,
                days=60,
                download_media=True
            )
            total_messages += count

        print(f"\n{'='*40}")
        print(f"🎉 Completed! Total messages: {total_messages}")
        print(f"⏱️ Total time: {(datetime.now(timezone.utc) - fetcher.start_time).total_seconds()/60:.1f} minutes")
        print(f"🚀 Speed: {total_messages/max(1, (datetime.now(timezone.utc) - fetcher.start_time).total_seconds()):.1f} msg/s")

        if fetcher.failed_channels:
            print(f"\n❌ Failed channels ({len(fetcher.failed_channels)}):")
            for channel in fetcher.failed_channels:
                print(f"- {channel}")

if __name__ == "__main__":
    asyncio.run(main())