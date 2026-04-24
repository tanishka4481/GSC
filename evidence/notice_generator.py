"""
PROVCHAIN — Notice Generator
============================
Populates legal notice templates with asset and scan data.
"""

import os
from jinja2 import Environment, FileSystemLoader

from core.config import get_settings
from registration.models import AssetRecord


def generate_notice(jurisdiction: str, asset: AssetRecord, infringing_urls: list[str], ipfs_cid: str) -> str:
    """
    Loads the appropriate Jinja2 template and populates it with asset, scan, 
    and owner data to produce a ready-to-send text string.
    
    Args:
        jurisdiction: 'dmca', 'it_rules', or 'copyright_act'
        asset: AssetRecord of the original content
        infringing_urls: List of URLs where unauthorized copies were found
        ipfs_cid: The IPFS CID of the final evidence bundle
        
    Returns:
        Rendered text content of the legal notice.
    """
    settings = get_settings()
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    
    env = Environment(loader=FileSystemLoader(template_dir))
    template_name = f"{jurisdiction}_notice.jinja2"
    
    try:
        template = env.get_template(template_name)
    except Exception:
        raise ValueError(f"Template for jurisdiction '{jurisdiction}' not found.")
    
    rendered_text = template.render(
        asset_id=asset.asset_id,
        sha256=asset.sha256,
        ipfs_cid=ipfs_cid or "PENDING_UPLOAD",
        created_at=asset.created_at,
        infringing_urls=infringing_urls,
        sender_name=settings.NOTICE_SENDER_NAME,
        sender_email=settings.NOTICE_SENDER_EMAIL,
        sender_address=settings.NOTICE_SENDER_ADDRESS,
    )
    
    return rendered_text
