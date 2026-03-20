"""Gzip compression middleware for Flask responses."""
import gzip
from io import BytesIO
from flask import request, Response

MIN_SIZE = 1024  # Only compress responses > 1KB
COMPRESSIBLE_TYPES = {'text/', 'application/json', 'application/javascript'}

def gzip_middleware(app):
    @app.after_request
    def compress(response: Response):
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if 'gzip' not in accept_encoding:
            return response
        if not response.content_type or response.content_length is not None and response.content_length < MIN_SIZE:
            return response
        if not any(response.content_type.startswith(t) for t in COMPRESSIBLE_TYPES):
            return response
        response.direct_passthrough = False
        data = response.get_data()
        if len(data) < MIN_SIZE:
            return response
        buf = BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=buf) as f:
            f.write(data)
        response.set_data(buf.getvalue())
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.get_data())
        response.headers['Vary'] = 'Accept-Encoding'
        return response
    return app


def optimize_payload(data):
    """Remove null fields and empty strings from dict/list."""
    if isinstance(data, dict):
        return {k: optimize_payload(v) for k, v in data.items() if v is not None and v != ''}
    if isinstance(data, list):
        return [optimize_payload(item) for item in data]
    return data
