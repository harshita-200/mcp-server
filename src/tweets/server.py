import logging
import json
from datetime import datetime
from typing import Any, Sequence
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
from pydantic import AnyUrl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tweets")

# Google Sheets API Configuration
API_KEY = "AIzaSyBHrlWiCscEPDW0JtgJ27B3sgLnUe_C14Y"
API_BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"
SPREADSHEET_ID = "1N4FhhBFXwRw2v_dnepaEUMUvRnV3rZkWvQTGkA0XlzE"
SHEET_NAME = "Sheet1"

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAIe1xQEAAAAAu%2F4q14btEBKIyYV2ooO7NM7HJwM%3DVyLfzQ8EtHfgTBr1US4kyQ4U1d2wMu2TE989S3xgEco4fOpHBr"

# Function to fetch Google Sheets data
async def fetch_google_sheet_data() -> dict[str, Any]:
    url = f"{API_BASE_URL}/{SPREADSHEET_ID}/values/{SHEET_NAME}!A1:Z?alt=json&key={API_KEY}"
    logger.debug(f"Fetching Google Sheet data from: {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        logger.info("Successfully fetched Google Sheet data")
        return {
            "project": "tweets",
            "sheet_name": SHEET_NAME,
            "range": data.get("range"),
            "values": data.get("values"),
            "timestamp": datetime.now().isoformat(),
        }
    except httpx.RequestError as e:
        logger.error(f"HTTP request error: {e}")
        raise RuntimeError(f"Request error: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP status error: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"HTTP error: {e.response.status_code} - {e.response.text}")

# Function to post tweet
async def post_tweet(tweet_text: str) -> dict[str, Any]:
    url = "https://api.twitter.com/2/tweets"
    try:
        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {"text": tweet_text} 
        logger.debug(f"Attempting to post tweet: {tweet_text}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)

        response.raise_for_status()

        if response.status_code == 201: 
            tweet_id = response.json()['data']['id']
            logger.info(f"Tweet posted successfully! Tweet ID: {tweet_id}")
            return response.json()
        else:
            logger.error(f"Error posting tweet: {response.status_code} - {response.text}")
            raise RuntimeError(f"Error posting tweet: {response.status_code} - {response.text}")
    except httpx.RequestError as e:
        logger.error(f"HTTPx RequestError encountered: {str(e)}")
        raise RuntimeError(f"HTTPx RequestError encountered: {str(e)}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPx HTTPStatusError: {e.response.status_code} - {e.response.text}")
        raise RuntimeError(f"HTTPx HTTP error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error posting tweet: {str(e)}")
        raise RuntimeError(f"Unexpected error posting tweet: {str(e)}")

app = Server("tweets")

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    if not str(uri).startswith("sheets://"):
        logger.error(f"Invalid resource URI: {uri}")
        raise ValueError(f"Unknown resource: {uri}")
    try:
        logger.debug(f"Reading resource for URI: {uri}")
        sheet_data = await fetch_google_sheet_data()
        return json.dumps(sheet_data, indent=2)
    except Exception as e:
        logger.error(f"Error reading resource: {str(e)}")
        raise RuntimeError(f"Error reading resource: {str(e)}")

@app.list_tools()
async def list_tools() -> list[dict[str, Any]]:
    logger.debug("Listing tools for MCP")
    return [
        {
            "name": "post_tweet",
            "description": "Post a tweet to Twitter.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tweet_text": {"type": "string", "description": "The text of the tweet to post."},
                },
                "required": ["tweet_text"],
            },
        },
        {
            "name": "sheets_fetch_sheet_data",
            "description": "Fetch data from a Google Sheet.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    logger.info(f"Tool called: {name}")
    if name == "sheets_fetch_sheet_data":
        try:
            logger.debug("Fetching Google Sheets data")
            sheet_data = await fetch_google_sheet_data()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(sheet_data, indent=2)
                )
            ]
        except Exception as e:
            logger.error(f"Google Sheets API error: {str(e)}")
            raise RuntimeError(f"Google Sheets API error: {str(e)}")
    elif name == "post_tweet":
        tweet_text = arguments.get("tweet_text")
        if not tweet_text:
            logger.error("Missing tweet_text in arguments")
            raise ValueError("Tweet text is required.")
        try:
            logger.debug("Posting tweet")
            tweet_response = await post_tweet(tweet_text)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(tweet_response, indent=2)
                )
            ]
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            raise RuntimeError(f"Error posting tweet: {str(e)}")
    else:
        logger.error(f"Unknown tool called: {name}")
        raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
