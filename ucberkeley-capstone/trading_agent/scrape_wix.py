#!/usr/bin/env python3
"""
Scrape Wix site and download all assets
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
import subprocess

def download_file(url, output_path):
    """Download a file using curl"""
    try:
        subprocess.run([
            'curl', '-L', '-s', '-o', str(output_path), url
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to download: {url}")
        return False

def extract_urls(html_content, base_url):
    """Extract all resource URLs from HTML"""
    urls = set()

    # CSS files
    urls.update(re.findall(r'href=["\']([^"\']+\.css[^"\']*)["\']', html_content))

    # JavaScript files
    urls.update(re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html_content))

    # Images
    urls.update(re.findall(r'src=["\']([^"\']+\.(?:jpg|jpeg|png|gif|svg|webp)[^"\']*)["\']', html_content, re.IGNORECASE))
    urls.update(re.findall(r'url\(["\']?([^"\'()]+\.(?:jpg|jpeg|png|gif|svg|webp)[^"\'()]*)["\']?\)', html_content, re.IGNORECASE))

    # Fonts
    urls.update(re.findall(r'url\(["\']?([^"\'()]+\.(?:woff|woff2|ttf|eot)[^"\'()]*)["\']?\)', html_content, re.IGNORECASE))

    # Make absolute URLs
    absolute_urls = set()
    for url in urls:
        if url.startswith('http'):
            absolute_urls.add(url)
        elif url.startswith('//'):
            absolute_urls.add('https:' + url)
        elif url.startswith('/'):
            absolute_urls.add(urljoin(base_url, url))

    return absolute_urls

def main():
    base_url = "https://studiomios.wixstudio.com/caramanta"
    output_dir = Path("caramanta_site")

    # Read the already downloaded HTML
    html_file = output_dir / "index.html"
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print(f"Extracting resource URLs from HTML...")
    urls = extract_urls(html_content, base_url)

    print(f"Found {len(urls)} resources to download")

    # Download resources
    for i, url in enumerate(urls, 1):
        parsed = urlparse(url)
        # Create directory structure
        path_parts = parsed.path.strip('/').split('/')

        if len(path_parts) > 1:
            resource_dir = output_dir / 'assets' / '/'.join(path_parts[:-1])
        else:
            resource_dir = output_dir / 'assets'

        resource_dir.mkdir(parents=True, exist_ok=True)

        filename = path_parts[-1] or 'index.html'
        output_path = resource_dir / filename

        print(f"[{i}/{len(urls)}] Downloading: {url[:80]}...")
        download_file(url, output_path)

    print(f"\nDone! Site downloaded to {output_dir}")
    print(f"Open {output_dir}/index.html in your browser")

if __name__ == "__main__":
    main()
