"""Bounded public-web fetcher with redirect and SSRF checks."""
from __future__ import annotations
import ipaddress, socket
from urllib.parse import urljoin, urlsplit
class FetchError(ValueError): pass
def _public_host(host, resolver=socket.getaddrinfo):
    if not host or host.lower()=="localhost" or host.endswith(".localhost"): raise FetchError("Local hostnames are not allowed")
    try: addresses=[ipaddress.ip_address(host)]
    except ValueError:
        try: records=resolver(host,None,type=socket.SOCK_STREAM)
        except OSError as exc: raise FetchError("Hostname could not be resolved") from exc
        addresses=[]
        for record in records:
            try: addresses.append(ipaddress.ip_address(record[4][0].split("%",1)[0]))
            except (ValueError,IndexError,TypeError): pass
    if not addresses or any(not a.is_global for a in addresses): raise FetchError("Private, reserved, or non-global destination is not allowed")
def validate_url(url, resolver=socket.getaddrinfo):
    if not isinstance(url,str) or len(url)>2048: raise FetchError("Invalid URL")
    p=urlsplit(url.strip())
    if p.scheme.lower() not in {"http","https"}: raise FetchError("Only HTTP and HTTPS URLs are allowed")
    if p.username or p.password or not p.hostname: raise FetchError("Credentials or missing hostname are not allowed")
    try: port=p.port
    except ValueError as exc: raise FetchError("Invalid port") from exc
    if port not in (None,80,443): raise FetchError("Non-standard ports are not allowed")
    _public_host(p.hostname,resolver); return p.geturl()
def fetch_public_page(url, *, session=None, timeout=12, max_bytes=1000000, max_redirects=3, resolver=socket.getaddrinfo):
    if not 1<=max_bytes<=5000000: raise ValueError("max_bytes must be between 1 and 5,000,000")
    if session is None:
        import requests; session=requests.Session()
    current=validate_url(url,resolver); headers={"User-Agent":"GoldNewsBot/3.0 (+public-news-reader)","Accept":"text/html,application/xhtml+xml"}
    for hop in range(max_redirects+1):
        response=session.get(current,headers=headers,timeout=timeout,stream=True,allow_redirects=False)
        if int(response.status_code) in (301,302,303,307,308):
            location=response.headers.get("Location")
            if not location or hop>=max_redirects: raise FetchError("Redirect limit reached or Location missing")
            current=validate_url(urljoin(current,location),resolver); continue
        response.raise_for_status(); ct=response.headers.get("Content-Type","").lower()
        if not ("text/html" in ct or "application/xhtml+xml" in ct): raise FetchError("Response is not HTML")
        declared=response.headers.get("Content-Length")
        if declared:
            try:
                if int(declared)>max_bytes: raise FetchError("Response exceeds size limit")
            except ValueError as exc: raise FetchError("Invalid Content-Length") from exc
        chunks=[]; size=0
        for chunk in response.iter_content(chunk_size=16384):
            if not chunk: continue
            size+=len(chunk)
            if size>max_bytes: raise FetchError("Response exceeds size limit")
            chunks.append(chunk)
        return b"".join(chunks).decode(getattr(response,"encoding",None) or "utf-8",errors="replace"),current
    raise FetchError("Redirect limit reached")
