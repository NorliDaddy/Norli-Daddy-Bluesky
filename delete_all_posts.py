#!/usr/bin/env python3
"""
Delete all posts from Bluesky account - use with caution!
"""

import logging
import os
import time
from dotenv import load_dotenv
from atproto import Client

load_dotenv()

# Bluesky Configuration
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_PASSWORD = os.getenv("BSKY_PASSWORD")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def delete_all_posts():
    """Delete all posts from the authenticated user's Bluesky account"""
    if not BSKY_HANDLE or not BSKY_PASSWORD:
        logging.error("Bluesky credentials not defined. Set BSKY_HANDLE and BSKY_PASSWORD in .env file")
        return
    
    try:
        # Login to Bluesky
        client = Client()
        client.login(BSKY_HANDLE.strip(), BSKY_PASSWORD.strip())
        logging.info(f"✅ Logged in as {BSKY_HANDLE}")
        
        # Get user's DID
        profile = client.get_profile(BSKY_HANDLE)
        user_did = profile.did
        logging.info(f"User DID: {user_did}")
        
        # Fetch all posts
        logging.info("Fetching all posts...")
        all_posts = []
        cursor = None
        
        while True:
            # Fetch feed with pagination
            from atproto import models
            response = client.app.bsky.feed.get_author_feed(
                params=models.AppBskyFeedGetAuthorFeed.Params(
                    actor=user_did,
                    limit=100,
                    cursor=cursor
                )
            )
            
            posts = response.feed
            if not posts:
                break
            
            # Filter for posts (not reposts or replies from others)
            for item in posts:
                post = item.post
                # Only include posts authored by this user
                if post.author.did == user_did:
                    all_posts.append(post)
            
            logging.info(f"Fetched {len(posts)} items (total user posts: {len(all_posts)})")
            
            # Check if there are more pages
            cursor = response.cursor
            if not cursor:
                break
            
            time.sleep(0.5)  # Be nice to the API
        
        logging.info(f"\n📊 Found {len(all_posts)} posts to delete\n")
        
        if not all_posts:
            logging.info("No posts found!")
            return
        
        # Ask for confirmation
        print(f"\n⚠️  WARNING: About to delete {len(all_posts)} posts from @{BSKY_HANDLE}")
        print("This action CANNOT be undone!")
        confirmation = input("\nType 'DELETE ALL' to confirm: ")
        
        if confirmation != "DELETE ALL":
            logging.info("Deletion cancelled")
            return
        
        # Delete each post
        logging.info("\n🗑️  Starting deletion process...\n")
        deleted_count = 0
        failed_count = 0
        
        for i, post in enumerate(all_posts, 1):
            try:
                # Extract the record key (rkey) from the URI
                # URI format: at://did:plc:xxx/app.bsky.feed.post/yyy
                rkey = post.uri.split('/')[-1]
                
                # Delete the post
                client.app.bsky.feed.post.delete(
                    repo=user_did,
                    rkey=rkey
                )
                
                deleted_count += 1
                logging.info(f"[{i}/{len(all_posts)}] ✅ Deleted post {rkey}")
                
                # Rate limiting - be nice to the API
                time.sleep(0.3)
                
            except Exception as e:
                failed_count += 1
                logging.error(f"[{i}/{len(all_posts)}] ❌ Failed to delete post {post.uri}: {e}")
        
        logging.info(f"\n{'='*60}")
        logging.info(f"DELETION COMPLETE")
        logging.info(f"{'='*60}")
        logging.info(f"✅ Successfully deleted: {deleted_count} posts")
        logging.info(f"❌ Failed: {failed_count} posts")
        logging.info(f"{'='*60}\n")
        
    except Exception as e:
        logging.error(f"Error during deletion: {e}")


if __name__ == "__main__":
    delete_all_posts()
