"""
Lightweight networking config shared by the scrapers and the proxy.

Kept SEPARATE from proxy.py (which pulls in Flask, ~100 ms) so importing a
scraper doesn't drag Flask into startup. The proxy server is now started lazily
on first playback instead of at launch.
"""

from curl_cffi import CurlOpt

# DoH TLS relax — some networks' DoH resolver has a self-signed / mismatched
# cert; without this, curl_cffi's DoH path fails. Harmless when DoH isn't used.
#
# CONNECTTIMEOUT caps the CONNECT phase (DNS + TCP + TLS) at 15 s on EVERY
# session that uses these options — so a dead host can never hang a request
# forever, even a call site that forgot an explicit ``timeout=``. It only limits
# connecting, NOT the transfer, so slow-but-alive streams are unaffected.
DNS_OPTIONS = {
    CurlOpt.DOH_SSL_VERIFYPEER: 0,
    CurlOpt.DOH_SSL_VERIFYHOST: 0,
    CurlOpt.CONNECTTIMEOUT: 15,
}
