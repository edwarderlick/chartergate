import os

original_unlink = os.unlink

def safe_unlink(path, *args, **kwargs):
    try:
        original_unlink(path, *args, **kwargs)
    except PermissionError as e:
        if "tmp" in str(path):
            pass # ignore Windows temp file locking bug
        else:
            raise

os.unlink = safe_unlink



def to_hex(addr_bytes):
    """Convert address bytes to checksummed hex matching contract output."""
    if hasattr(addr_bytes, "as_hex"):
        return addr_bytes.as_hex
    from genlayer.py.types import Address

    return Address(addr_bytes).as_hex
