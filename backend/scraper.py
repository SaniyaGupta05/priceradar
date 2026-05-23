"""
PriceRadar Scraper
- Zepto & Blinkit: network interception of API JSON → exact prices
- BigBasket & Instamart: DOM JS extraction
"""
import re, time, random, logging, json, concurrent.futures
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

def _make_ctx(playwright, headless=True, lat=None, lng=None, storage_state=None):
    import os
    ua = USER_AGENTS[0] if storage_state else random.choice(USER_AGENTS)
    cv = re.search(r"Chrome/(\d+)", ua); ver = cv.group(1) if cv else "124"
    browser = playwright.chromium.launch(headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-extensions",
            "--js-flags=--max-old-space-size=128"
        ])
    latitude = lat if lat is not None else 12.9716
    longitude = lng if lng is not None else 77.5946
    
    context_opts = {
        "user_agent": ua,
        "viewport": {"width":1366,"height":768},
        "locale": "en-US,en;q=0.9",
        "timezone_id": "Asia/Kolkata",
        "geolocation": {"latitude":latitude,"longitude":longitude},
    }
    if not storage_state:
        context_opts["extra_http_headers"] = {
            "accept":"text/html,application/xhtml+xml,*/*;q=0.8",
            "accept-language":"en-US,en;q=0.9",
            "sec-ch-ua":f'"Not_A Brand";v="8","Chromium";v="{ver}","Google Chrome";v="{ver}"',
            "sec-ch-ua-mobile":"?0","sec-ch-ua-platform":'"Windows"',
            "sec-fetch-dest":"document","sec-fetch-mode":"navigate",
            "sec-fetch-site":"none","upgrade-insecure-requests":"1",
        }
    if storage_state and os.path.exists(storage_state):
        context_opts["storage_state"] = storage_state

    ctx = browser.new_context(**context_opts)
    ctx.grant_permissions(["geolocation"])
    ctx.add_init_script("""
        Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
        Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3]});
        Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
        window.chrome={runtime:{}};
    """)
    return browser, ctx

def _encode(s):
    import urllib.parse
    return urllib.parse.quote(s)

def encodeURIComponent(s):
    import urllib.parse
    return urllib.parse.quote(s)

# ══════════════════════════════════════════════════════════════════════════════
#  ZEPTO  —  dedicated, self-contained scraper
#  API endpoint: bff-gateway.zepto.com/user-search-service/api/v3/search
#  Link format:  zeptonow.com/pn/{nameSlug}/pvid/{variantId}
# ══════════════════════════════════════════════════════════════════════════════

def _zepto_slug(text: str) -> str:
    """Generate a URL-safe slug from a product name (matches Zepto's format)."""
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _zepto_price(val) -> float:
    """Convert Zepto price value to rupees (values > 1000 are in paise)."""
    if not val: return 0.0
    v = float(val)
    return v / 100.0 if v > 1000 else v


def _zepto_collect_items(obj, results, depth=0):
    """
    Recursively walk any JSON structure and collect all Zepto product items.
    A product item is a dict that directly contains both 'product' and
    'productVariant' keys with the product name inside 'product'.
    Unlike the old walk, this continues to recurse siblings after finding an item.
    """
    if depth > 15:
        return
    if isinstance(obj, dict):
        if ('product' in obj
                and isinstance(obj.get('product'), dict)
                and obj['product'].get('name')):
            results.append(obj)
            return   # don't recurse into this item's children
        for v in obj.values():
            _zepto_collect_items(v, results, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _zepto_collect_items(v, results, depth + 1)


def _zepto_parse_item(item: dict) -> dict | None:
    """Convert a raw Zepto API item dict into our standard product dict."""
    import urllib.parse

    # Skip only when the field is explicitly True
    prod = item.get('product') or {}
    pv   = item.get('productVariant') or {}
    if (item.get('outOfStock') is True or 
        item.get('isOutOfStock') is True or 
        item.get('out_of_stock') is True or
        pv.get('outOfStock') is True or 
        pv.get('isOutOfStock') is True or 
        pv.get('out_of_stock') is True or
        item.get('stock') == 0 or
        pv.get('stock') == 0):
        return None
    name = prod.get('name') or item.get('name') or ''
    if not name:
        return None

    # ── Price (paise or rupees, auto-detected) ──
    mrp_raw   = item.get('mrp') or pv.get('mrp') or item.get('sellingPrice') or 0
    price_raw = (item.get('discountedSellingPrice')
                 or item.get('sellingPrice')
                 or mrp_raw)
    price = _zepto_price(price_raw)
    mrp   = _zepto_price(mrp_raw)
    if price <= 0:
        return None

    # ── Quantity ──
    quantity = (pv.get('formattedPacksize')
                or pv.get('packsize')
                or item.get('quantity')
                or '')

    # ── Image ──
    images   = pv.get('images') or prod.get('images') or []
    img_path = ''
    if images and isinstance(images[0], dict):
        img_path = (images[0].get('path') or images[0].get('url') or '').lstrip('/')
    if img_path and not img_path.startswith('http'):
        # Using tr:w-400/ to fetch optimized responsive sizes from Zepto's CDN
        image = f"https://cdn.zeptonow.com/production/tr:w-400/{img_path}"
    else:
        image = img_path

    # ── Rating ──
    rating = float((pv.get('ratingSummary') or {}).get('averageRating') or 0.0)

    # ── Direct product link ──
    # Priority: pv.nameSlug > prod.nameSlug > generated slug
    name_slug  = pv.get('nameSlug') or prod.get('nameSlug') or ''
    variant_id = pv.get('id') or ''

    # Fallback: generate slug from the product name (Zepto uses same pattern)
    if not name_slug:
        clean_name = name.split('|')[0].strip()
        name_slug  = _zepto_slug(clean_name)

    # Fallback: use product id or top-level item id as variant id
    if not variant_id:
        variant_id = prod.get('id') or item.get('id') or ''

    if name_slug and variant_id:
        link = f"https://www.zeptonow.com/pn/{name_slug}/pvid/{variant_id}"
    else:
        # Last resort: simple keyword search (name without pipe)
        kw   = name.split('|')[0].strip()
        link = f"https://www.zeptonow.com/search?query={urllib.parse.quote(kw)}"

    return {
        'name':     name,
        'price':    price,
        'mrp':      mrp,
        'quantity': str(quantity),
        'image':    image,
        'link':     link,
        'rating':   rating,
    }


def scrape_zepto(query: str, lat=None, lng=None) -> list:
    """
    Scrape Zepto by intercepting the bff-gateway search API.
    Returns up to 10 products with direct /pn/{slug}/pvid/{id} links.
    """
    import urllib.parse
    url = f"https://www.zeptonow.com/search?query={urllib.parse.quote(query)}"

    # All known Zepto search API endpoint patterns (kept broad to survive endpoint changes)
    ZEPTO_API_PATTERNS = [
        'bff-gateway.zepto',
        'user-search-service',
        'search-service',
        'api/v3/search',
        'api/v2/search',
        'api/v4/search',
        'api/v1/search',
        'api.zeptonow.com',
        'catalog',
        'zeptonow.com/api',
    ]

    raw_responses = []   # will hold parsed JSON from API calls
    products      = []

    try:
        with sync_playwright() as pw:
            browser, ctx = _make_ctx(pw, lat=lat, lng=lng)
            page = ctx.new_page()

            # ── Response interceptor ──────────────────────────────────────────
            def on_response(resp):
                try:
                    url_lower = resp.url.lower()
                    ct        = resp.headers.get('content-type', '')
                    if 'json' not in ct:
                        return
                    if not any(pat in url_lower for pat in ZEPTO_API_PATTERNS):
                        return
                    if 'filters' in url_lower:   # skip filter metadata endpoint
                        return
                    data = resp.json()
                    raw_responses.append(data)
                    log.info(f"[Zepto] Captured API: {resp.url[:90]}")
                except Exception as exc:
                    log.debug(f"[Zepto] response cb error: {exc}")

            page.on('response', on_response)

            try:
                # ── Load page ─────────────────────────────────────────────────
                page.goto(url, wait_until='domcontentloaded', timeout=55000)
                try:
                    page.wait_for_load_state('networkidle', timeout=12000)
                except Exception:
                    pass
                
                # Smart wait loop instead of hardcoded sleeps
                start_time = time.time()
                while time.time() - start_time < 8:
                    # Let's count items in raw_responses to see if we have enough data
                    temp_items = []
                    for response_data in raw_responses:
                        _zepto_collect_items(response_data, temp_items)
                    if len(temp_items) >= 5:
                        log.info(f"[Zepto] Smart break: captured {len(temp_items)} items early")
                        break
                    time.sleep(0.4)

                # Scroll a bit only if we didn't capture enough products
                temp_items = []
                for response_data in raw_responses:
                    _zepto_collect_items(response_data, temp_items)
                if len(temp_items) < 3:
                    for i in range(1, 4):
                        page.evaluate(f"window.scrollTo(0, {i * 300})")
                        time.sleep(0.4)
                    time.sleep(1.0)

            finally:
                page.close()
                ctx.close()
                browser.close()

        # ── Parse every captured API response ─────────────────────────────────
        all_items = []
        for response_data in raw_responses:
            _zepto_collect_items(response_data, all_items)

        log.info(f"[Zepto] Collected {len(all_items)} raw items from "
                 f"{len(raw_responses)} API responses")

        # ── DOM fallback: if API interception got nothing, scrape the DOM ──────
        if not all_items and not raw_responses:
            log.warning("[Zepto] API interception yielded nothing — trying DOM fallback")
            try:
                with sync_playwright() as pw2:
                    browser2, ctx2 = _make_ctx(pw2, lat=lat, lng=lng)
                    page2 = ctx2.new_page()
                    try:
                        page2.goto(url, wait_until='domcontentloaded', timeout=45000)
                        try:
                            page2.wait_for_load_state('networkidle', timeout=12000)
                        except Exception:
                            pass
                        import time as _time
                        _time.sleep(5)
                        for i in range(1, 7):
                            page2.evaluate(f"window.scrollTo(0, {i * 400})")
                            _time.sleep(0.4)
                        dom_items = page2.evaluate(_ZEPTO_DOM) or []
                        log.info(f"[Zepto] DOM fallback returned {len(dom_items)} items")
                        for di in dom_items:
                            # Wrap DOM items in a fake API-item shape so the
                            # existing parser can normalise them
                            name = di.get('name', '')
                            if not name:
                                continue
                            products.append({
                                'source':   'Zepto',
                                'name':     name,
                                'price':    float(di.get('price') or 0),
                                'mrp':      max(float(di.get('mrp') or di.get('price') or 0),
                                               float(di.get('price') or 0)),
                                'quantity': str(di.get('quantity', '')),
                                'link':     di.get('link', ''),
                                'image':    di.get('image', ''),
                                'rating':   float(di.get('rating') or 0),
                            })
                    finally:
                        page2.close()
                        ctx2.close()
                        browser2.close()
            except Exception as dom_exc:
                log.error(f"[Zepto] DOM fallback error: {dom_exc}")

        # ── Convert to product dicts and deduplicate ──────────────────────────
        seen = set()
        for item in all_items:
            p = _zepto_parse_item(item)
            if not p:
                continue
            key = f"{p['name'].lower()[:40]}_{p['price']}"
            if key in seen:
                continue
            seen.add(key)
            products.append({
                'source':   'Zepto',
                'name':     p['name'],
                'price':    p['price'],
                'mrp':      max(p['mrp'], p['price']),
                'quantity': p['quantity'],
                'link':     p['link'],
                'image':    p['image'],
                'rating':   p['rating'],
            })

        # Log link quality
        direct  = sum(1 for p in products if '/pn/' in p['link'])
        fallback = len(products) - direct
        log.info(f"[Zepto] {len(products)} products | "
                 f"{direct} direct /pn/ links | {fallback} search fallbacks")

    except Exception as exc:
        log.error(f"[Zepto] Fatal: {exc}")

    return products[:10]


# ── Blinkit API Parser ───────────────────────────────────────────────────────
def _parse_blinkit_api(data):
    products = []
    snippets = data.get('response', {}).get('snippets', [])
    for sn in snippets:
        sdata = sn.get('data', {})
        if not sdata: continue
        
        product_id = sdata.get('product_id')
        atc = sdata.get('atc_action', {})
        cart_item = atc.get('add_to_cart', {}).get('cart_item', {}) if atc else {}
        
        if not product_id and not cart_item:
            continue
            
        if (sdata.get('is_sold_out', False) or 
            sdata.get('sold_out', False) or 
            sdata.get('out_of_stock', False) or
            sdata.get('stock', 1) == 0):
            continue
            
        name = cart_item.get('product_name') or sdata.get('display_name') or sdata.get('name', {}).get('text')
        if not name: continue
        
        price = cart_item.get('price')
        mrp = cart_item.get('mrp')
        
        if price is None:
            price_text = sdata.get('normal_price', {}).get('text', '')
            try:
                price = float(price_text.replace('₹', '').replace(',', '').strip())
            except:
                price = 0.0
                
        if mrp is None:
            mrp_text = sdata.get('mrp', {}).get('text', '')
            try:
                mrp = float(mrp_text.replace('₹', '').replace(',', '').strip())
            except:
                mrp = price
                
        if not price or price <= 0: continue
        
        quantity = cart_item.get('unit') or sdata.get('variant', {}).get('text', '')
        image = cart_item.get('image_url') or sdata.get('media_container', {}).get('items', [{}])[0].get('image', {}).get('url', '')
        
        rating = 0.0
        rating_obj = sdata.get('rating', {})
        if rating_obj:
            if rating_obj.get('type') == 'bar':
                rating = float(rating_obj.get('bar', {}).get('value') or 0.0)
            else:
                rating = float(rating_obj.get('value') or 0.0)
                
        pid = product_id or cart_item.get('product_id')
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') if isinstance(name, str) else ''
        link = f"https://blinkit.com/prn/{slug}/prid/{pid}" if pid else f"https://blinkit.com/s/?q={_encode(name)}"
        
        products.append({
            'name': name,
            'price': float(price),
            'mrp': float(mrp),
            'quantity': str(quantity),
            'image': image,
            'link': link,
            'rating': rating
        })
    return products

# ── Swiggy Instamart API Parser ────────────────────────────────────────
def _parse_instamart_api(data):
    products = []
    def walk(obj):
        if isinstance(obj, dict):
            if "displayName" in obj and "variations" in obj and isinstance(obj["variations"], list):
                for var in obj["variations"]:
                    instock = var.get("inventory", {}).get("inStock", True)
                    if not instock:
                        continue
                    
                    v_name = var.get("displayName") or obj.get("displayName") or ""
                    if not v_name:
                        continue
                        
                    price_obj = var.get("price", {})
                    off_price = price_obj.get("offerPrice", {})
                    mrp_price = price_obj.get("mrp", {})
                    
                    try:
                        price = float(off_price.get("units", 0)) + float(off_price.get("nanos", 0)) / 1e9
                        mrp = float(mrp_price.get("units", 0)) + float(mrp_price.get("nanos", 0)) / 1e9
                    except (ValueError, TypeError):
                        continue
                        
                    if price <= 0:
                        continue
                        
                    qty = var.get("quantityDescription") or ""
                    
                    img_ids = var.get("imageIds") or []
                    img_id = img_ids[0] if img_ids else ""
                    image = ""
                    if img_id:
                        if img_id.startswith("http"):
                            image = img_id
                        else:
                            image = f"https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_250/{img_id}"
                    
                    rating_val = 0.0
                    rating_obj = var.get("rating", {})
                    if rating_obj:
                        try:
                            rating_val = float(rating_obj.get("value") or 0.0)
                        except:
                            pass
                            
                    sku_id = var.get("skuId") or ""
                    link = f"https://www.swiggy.com/instamart/item/{sku_id}" if sku_id else f"https://www.swiggy.com/instamart/search?query={_encode(v_name)}"
                    
                    products.append({
                        'name': v_name,
                        'price': price,
                        'mrp': max(mrp, price),
                        'quantity': str(qty),
                        'image': image,
                        'link': link,
                        'rating': rating_val
                    })
            else:
                for v in obj.values():
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
                
    walk(data)
    return products

# ── Intercept Helper ─────────────────────────────────────────────────────────
def _scrape_with_intercept(source, url, api_patterns, api_parser_fn, dom_js_fallback,
                            setup_fn=None, wait_sel=None, limit=10, lat=None, lng=None, storage_state=None):
    products = []
    try:
        with sync_playwright() as p:
            browser, ctx = _make_ctx(p, lat=lat, lng=lng, storage_state=storage_state)
            if setup_fn: setup_fn(ctx)
            page = ctx.new_page()
            api_hits = []
            intercepted_urls = []

            def on_response(resp):
                try:
                    url_lower = resp.url.lower()
                    if any(pat.lower() in url_lower for pat in api_patterns):
                        ct = resp.headers.get('content-type', '')
                        if 'json' in ct:
                            try:
                                data = resp.json()
                            except Exception:
                                return
                            intercepted_urls.append(resp.url)
                            parsed = api_parser_fn(data)
                            if parsed:
                                log.info(f"[{source}] API hit {resp.url[:100]} → {len(parsed)} items")
                                api_hits.extend(parsed)
                            else:
                                log.info(f"[{source}] API hit {resp.url[:100]} → 0 items (no match)")
                except Exception as e:
                    log.debug(f"[{source}] response handler error: {e}")

            page.on('response', on_response)
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=50000)
                try: page.wait_for_load_state('networkidle', timeout=12000)
                except: pass
                
                # Smart wait loop instead of fixed sleep
                start_time = time.time()
                while time.time() - start_time < 8:
                    if len(api_hits) >= 5:
                        log.info(f"[{source}] Smart break: captured {len(api_hits)} API items early")
                        break
                    time.sleep(0.4)
                
                if len(api_hits) < 3:
                    if wait_sel:
                        try: page.wait_for_selector(wait_sel, timeout=4000)
                        except: pass
                    # Scroll to trigger lazy-load API calls
                    for i in range(1, 4):
                        page.evaluate(f"window.scrollTo(0,{i*400})")
                        time.sleep(0.4)
                    time.sleep(1.0)
                    
                log.info(f"[{source}] Intercepted {len(intercepted_urls)} API URLs")

                raw_items = []
                if api_hits:
                    log.info(f"[{source}] Using API data: {len(api_hits)} raw items")
                    raw_items = api_hits
                else:
                    log.info(f"[{source}] No API data, using DOM fallback")
                    raw_items = page.evaluate(dom_js_fallback) or []

                seen = set()
                for it in raw_items:
                    name = (it.get('name') or '').strip()
                    price = float(it.get('price') or 0)
                    if not name or price <= 0: continue
                    key = f"{name.lower()[:30]}_{price}"
                    if key in seen: continue
                    seen.add(key)
                    mrp = max(float(it.get('mrp') or price), price)
                    lnk = it.get('link', '')
                    if source == 'Instamart' and not lnk:
                        lnk = f"https://www.swiggy.com/instamart/search?query={_encode(name)}"
                    if not lnk:
                        lnk = url
                    if source == 'Zepto' and not lnk.startswith('http'):
                        lnk = f"https://www.zeptonow.com/search?query={_encode(name)}"
                    products.append({
                        'source': source, 'name': name, 'price': price, 'mrp': mrp,
                        'quantity': it.get('quantity',''),
                        'link': lnk, 'image': it.get('image',''),
                        'rating': float(it.get('rating') or 0),
                    })
            finally:
                page.close(); ctx.close(); browser.close()
    except Exception as e:
        log.error(f"[{source}] Fatal: {e}")
    log.info(f"[{source}] Returning {len(products)} products")
    return products[:limit]

# ── BigBasket DOM extractor ──────────────────────────────────────────────────
_BB_JS = r"""() => {
    const R = [];
    let cards = [...document.querySelectorAll('li.PaginateItems___StyledLi')];
    if (!cards.length) cards = [...document.querySelectorAll('[class*="SKUCard"],[class*="sku-card"]')];
    if (!cards.length){const seen=new Set();document.querySelectorAll('a[href*="/pd/"]').forEach(a=>{const c=a.closest('li')||a.closest('[class*="card" i]');if(c&&!seen.has(c)){seen.add(c);cards.push(c);}});}
    const firstLine=el=>el?el.innerText.split('\n')[0].trim():'';
    const isOOS = (c) => {
        const t = (c.innerText || '').toLowerCase();
        const keywords = ['out of stock', 'out ofstock', 'notify me', 'sold out', 'unavailable', 'currently unavailable', 'coming soon', 'not available'];
        if (keywords.some(k => t.includes(k))) return true;
        const btns = [...c.querySelectorAll('button, a, div[role="button"]')];
        for (const b of btns) {
            const bt = (b.innerText || '').toLowerCase();
            if (b.disabled || b.getAttribute('disabled') !== null || keywords.some(k => bt.includes(k))) return true;
        }
        return false;
    };
    cards.forEach(card=>{
        const txt=card.innerText||'';
        if(isOOS(card))return;
        if(!txt.includes('\u20b9'))return;
        const linkEl=card.querySelector('a[href*="/pd/"]');
        const slugHref=linkEl?linkEl.getAttribute('href'):'';
        const slugMatch=slugHref.match(/\/pd\/\d+\/([^/?]+)/);
        let name='';
        if(slugMatch){name=slugMatch[1].replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase()).trim();name=name.replace(/\s+\d+\s*(G|Kg|Ml|L|Gm|Gms|Pack|Pcs)$/i,'').trim();}
        if(!name){const h2=card.querySelector('h2'),h3=card.querySelector('h3');const b=h2?firstLine(h2):'',p=h3?firstLine(h3):'';name=(b&&p&&p!==b)?b+' '+p:p||b;}
        if(!name)return;
        const priceSpans=[...card.querySelectorAll('span,p')].filter(el=>/^\s*\u20b9\s*\d+(?:\.\d+)?\s*$/.test(el.innerText)).map(el=>parseFloat(el.innerText.replace(/[^\d.]/g,''))).filter(p=>p>=5).sort((a,b)=>a-b);
        let price=priceSpans.length?priceSpans[0]:0,mrp=priceSpans.length>1?priceSpans[priceSpans.length-1]:price;
        if(!price){const clean=txt.split('\n').filter(l=>!/you save|save:|har din|% off|\d+%/i.test(l)).join('\n');const ps=[...clean.matchAll(/\u20b9\s*(\d+(?:\.\d+)?)/g)].map(m=>parseFloat(m[1])).filter(p=>p>=5).sort((a,b)=>a-b);if(ps.length){price=ps[0];mrp=ps[ps.length-1];}}
        if(!mrp||mrp<price)mrp=price;
        if(!name||!price)return;
        const link=slugHref.startsWith('/')?'https://www.bigbasket.com'+slugHref:slugHref;
        const img=card.querySelector('img');const imgSrc=img?(img.src||img.dataset.src||''):'';
        const qty=(txt.match(/(\d+(?:\.\d+)?)\s*(kg|g|ml|l|gm|gms|pcs?|pack)/i)||[''])[0];
        const rat=parseFloat((txt.match(/\b([1-5]\.[0-9])\b/)||['','0'])[1])||0;
        R.push({name,price,mrp,quantity:qty.trim(),link,rating:rat,image:imgSrc.startsWith('//')?'https:'+imgSrc:imgSrc});
    });
    return R;
}"""

# ── Blinkit DOM extractor (fallback if network fails) ───────────────────────
_BLINKIT_JS = r"""() => {
    const R = [];
    const getPricesFromCard = (card) => {
        const elements = [...card.querySelectorAll('span, div, p, strong')].filter(el => {
            if (!/\u20b9\s*\d+/.test(el.innerText)) return false;
            let current = el;
            const badgeRegex = /discount|offer|badge|saving|promo|tag/i;
            const offerRegex = /off|offer|save|saved|cashback|%|disc|free/i;
            while (current && current !== card) {
                const className = (current.className && typeof current.className === 'string') ? current.className : '';
                const id = (current.id && typeof current.id === 'string') ? current.id : '';
                if (badgeRegex.test(className + ' ' + id)) return false;
                if (current === el && offerRegex.test(el.innerText || '')) return false;
                current = current.parentElement;
            }
            const childHasPrice = [...el.children].some(child => /\u20b9\s*\d+/.test(child.innerText));
            if (childHasPrice) return false;
            return true;
        });
        const prices = elements.map(el => {
            const match = el.innerText.match(/\u20b9\s*(\d+(?:\.\d+)?)/);
            return match ? parseFloat(match[1]) : null;
        }).filter(v => v !== null && v > 0);
        const uniquePrices = [];
        prices.forEach(p => {
            if (!uniquePrices.includes(p)) uniquePrices.push(p);
        });
        return uniquePrices;
    };

    let cards = [...document.querySelectorAll('div[id]')].filter(d => /^\d{4,}$/.test(d.id));
    if (!cards.length) cards = [...document.querySelectorAll('[class*="Product__UpdatedPlpProductContainer"],[data-testid="product-card"]')];
    
    const isOOS = (c) => {
        const t = (c.innerText || '').toLowerCase();
        const keywords = ['out of stock', 'out ofstock', 'notify me', 'sold out', 'unavailable', 'currently unavailable', 'coming soon', 'not available'];
        if (keywords.some(k => t.includes(k))) return true;
        const btns = [...c.querySelectorAll('button, a, div[role="button"]')];
        for (const b of btns) {
            const bt = (b.innerText || '').toLowerCase();
            if (b.disabled || b.getAttribute('disabled') !== null || keywords.some(k => bt.includes(k))) return true;
        }
        return false;
    };
    cards.forEach(card => {
        const txt = card.innerText || '';
        if (isOOS(card)) return;
        
        const nEl = card.querySelector('[class*="PLPName"],[class*="product-name" i],h3,h4,h5');
        let name = nEl ? nEl.innerText.trim() : '';
        if (!name) {
            const ls = txt.split('\n').map(l => l.trim()).filter(l => l.length > 3);
            name = ls.find(l => !l.includes('\u20b9') && !/off|mrp|add|min|%|\d+\s*(kg|g|ml|l)/i.test(l)) || '';
        }
        if (!name) return;
        
        const prices = getPricesFromCard(card);
        if (!prices.length) return;
        
        const price = prices[0];
        const mrp = prices.length > 1 ? prices[1] : price;
        
        const img = card.querySelector('img');
        const imgSrc = img ? (img.src || img.dataset.src || '') : '';
        const qty = (txt.match(/(\d+(?:\.\d+)?)\s*(kg|g|ml|l|gm|gms|pcs?|pack)/i) || [''])[0];
        const id = card.id || '';
        const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        const link = id ? `https://blinkit.com/prn/${slug}/prid/${id}` : `https://blinkit.com/s/?q=${encodeURIComponent(name)}`;
        const rat = parseFloat((txt.match(/\b([1-5]\.[0-9])\b/) || ['', '0'])[1]) || 0;
        
        R.push({
            name,
            price,
            mrp,
            quantity: qty.trim(),
            link,
            rating: rat,
            image: imgSrc.startsWith('//') ? 'https:' + imgSrc : imgSrc
        });
    });
    return R;
}"""

# ── Instamart DOM extractor ──────────────────────────────────────────────────
_INSTAMART_JS = r"""() => {
    const R = [];
    const imgs = [...document.querySelectorAll('img')];
    const seen = new Set();
    
    const isOOS = (c) => {
        const t = (c.innerText || '').toLowerCase();
        const keywords = ['out of stock', 'out ofstock', 'notify me', 'sold out', 'unavailable', 'currently unavailable', 'coming soon', 'not available'];
        if (keywords.some(k => t.includes(k))) return true;
        const btns = [...c.querySelectorAll('button, a, div[role="button"]')];
        for (const b of btns) {
            const bt = (b.innerText || '').toLowerCase();
            if (b.disabled || b.getAttribute('disabled') !== null || keywords.some(k => bt.includes(k))) return true;
        }
        return false;
    };
    
    imgs.forEach(img => {
        let p = img.parentElement;
        let card = null;
        for (let i = 0; i < 8; i++) {
            if (!p || p.tagName === 'BODY' || p.tagName === 'HTML') break;
            const txt = p.innerText || '';
            const lines = txt.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            const hasQty = /(\d+(?:\.\d+)?)\s*(kg|g|ml|l|gm|gms|pcs?|pack)/i.test(txt);
            const hasPrice = lines.some(l => /^\d+$/.test(l));
            if (hasQty && hasPrice) {
                card = p;
            }
            p = p.parentElement;
        }
        if (card && !seen.has(card)) {
            seen.add(card);
            if (isOOS(card)) return;
            
            const txt = card.innerText || '';
            const lines = txt.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            
            // Clean lines for product name
            const cleanLines = lines.filter(l => !/mins|ad|sold out|sponsored|off|%|mrp|sponsored/i.test(l) && !/^\d+$/.test(l) && l.length > 2);
            const name = cleanLines[0] || '';
            
            // Find price lines (numbers only)
            const priceLines = lines.filter(l => /^\d+$/.test(l));
            let price = priceLines.length > 0 ? parseFloat(priceLines[priceLines.length - 1]) : 0;
            let mrp = price;
            
            // Handle discount structure e.g. "6% OFF", "31", "33"
            const discountLineIdx = lines.findIndex(l => /% off/i.test(l));
            if (discountLineIdx !== -1 && discountLineIdx + 2 < lines.length) {
                const p1 = parseFloat(lines[discountLineIdx + 1]);
                const p2 = parseFloat(lines[discountLineIdx + 2]);
                if (!isNaN(p1) && !isNaN(p2)) {
                    price = Math.min(p1, p2);
                    mrp = Math.max(p1, p2);
                }
            }
            
            const qty = (txt.match(/(\d+(?:\.\d+)?)\s*(kg|g|ml|l|gm|gms|pcs?|pack)/i) || [''])[0];
            
            if (name && price > 0) {
                let link = '';
                const aEls = [...card.querySelectorAll('a')];
                if (card.tagName === 'A') aEls.push(card);
                for (const a of aEls) {
                    const href = a.getAttribute('href') || '';
                    if (href.includes('/item/') || href.includes('/instamart/')) {
                        link = href.startsWith('http') ? href : 'https://www.swiggy.com' + (href.startsWith('/') ? '' : '/') + href;
                        break;
                    }
                }
                if (!link && aEls.length > 0) {
                    const href = aEls[0].getAttribute('href') || '';
                    if (href) {
                        link = href.startsWith('http') ? href : 'https://www.swiggy.com' + (href.startsWith('/') ? '' : '/') + href;
                    }
                }
                R.push({
                    name,
                    price,
                    mrp,
                    quantity: qty.trim(),
                    link: link,
                    rating: 0,
                    image: img.src || img.dataset.src || ''
                });
            }
        }
    });
    return R;
}"""

# ── Zepto DOM Fallback Javascript ────────────────────────────────────────────
# Tries multiple card selectors used by current & past Zepto layouts
_ZEPTO_DOM = r"""() => {
    const R = [];
    const getPrices = (card) => {
        const all = [...card.querySelectorAll('span,p,div,strong')];
        const prices = [];
        all.forEach(el => {
            const t = el.innerText || '';
            if (!/\u20b9/.test(t)) return;
            // skip elements whose children also have prices (container elements)
            if ([...el.children].some(c => /\u20b9/.test(c.innerText || ''))) return;
            const m = t.match(/\u20b9\s*(\d+(?:\.\d+)?)/);
            if (m) prices.push(parseFloat(m[1]));
        });
        const unique = [...new Set(prices)].filter(p => p > 0).sort((a,b)=>a-b);
        return unique;
    };

    // Multiple strategies to find product cards on Zepto
    let cards = [];

    // Strategy 1: anchor tags with /pn/ (product-name) in href
    if (!cards.length) cards = [...document.querySelectorAll('a[href*="/pn/"]')];

    // Strategy 2: data-testid attributes common in Zepto
    if (!cards.length) cards = [...document.querySelectorAll('[data-testid*="product"],[data-testid*="item"],[data-testid*="card"]')];

    // Strategy 3: class name patterns
    if (!cards.length) cards = [...document.querySelectorAll(
        '[class*="ProductCard"],[class*="product-card"],[class*="ItemCard"],[class*="item-card"],[class*="plp-product"],[class*="search-result"]'
    )].filter(el => el.querySelector('img') && /\u20b9/.test(el.innerText || ''));

    // Strategy 4: generic heuristic — small divs/lis with price and image
    if (!cards.length) {
        cards = [...document.querySelectorAll('div,li,article')].filter(el => {
            const t = el.innerText || '';
            return /\u20b9/.test(t) && el.querySelector('img') &&
                   el.children.length >= 2 && el.children.length <= 12 &&
                   !['BODY','HEADER','MAIN','NAV','FOOTER','SECTION','UL','OL'].includes(el.tagName) &&
                   el.offsetHeight > 100 && el.offsetHeight < 700 && el.offsetWidth > 80;
        }).slice(0, 30);
    }

    const isOOS = (c) => {
        const t = (c.innerText || '').toLowerCase();
        const keywords = ['out of stock', 'out ofstock', 'notify me', 'sold out', 'unavailable', 'currently unavailable', 'coming soon', 'not available'];
        if (keywords.some(k => t.includes(k))) return true;
        const btns = [...c.querySelectorAll('button, a, div[role="button"]')];
        for (const b of btns) {
            const bt = (b.innerText || '').toLowerCase();
            if (b.disabled || b.getAttribute('disabled') !== null || keywords.some(k => bt.includes(k))) return true;
        }
        return false;
    };
    cards.forEach(card => {
        const txt = card.innerText || '';
        if (isOOS(card)) return;

        // Try to extract name from known element types
        const nameEl = card.querySelector(
            'h5,h4,h3,[class*="name" i],[class*="title" i],[class*="product-name" i],[data-testid*="name"]'
        );
        let name = nameEl ? nameEl.innerText.trim() : '';
        if (!name) {
            const lines = txt.split('\n').map(l => l.trim()).filter(l => l.length > 3 && l.length < 120);
            name = lines.find(l => !l.includes('\u20b9') && !/^(add|notify|off|%|mrp|\d+)/i.test(l)) || '';
        }
        if (!name || name.length < 3) return;

        const prices = getPrices(card);
        if (!prices.length) return;
        const price = prices[0];
        const mrp   = prices.length > 1 ? prices[prices.length-1] : price;

        const img    = card.querySelector('img');
        const imgSrc = img ? (img.src || img.dataset.src || img.dataset.lazySrc || '') : '';
        const qty    = (txt.match(/(\d+(?:\.\d+)?)\s*(kg|g|ml|l|gm|gms|pcs?|pack)/i) || [''])[0];
        const rat    = parseFloat((txt.match(/\b([1-5]\.[0-9])\b/) || ['','0'])[1]) || 0;
        const sn     = encodeURIComponent(name.split('|')[0].trim());

        R.push({
            name, price, mrp,
            quantity: qty.trim(),
            link: `https://www.zeptonow.com/search?query=${sn}`,
            rating: rat,
            image: imgSrc.startsWith('//') ? 'https:' + imgSrc : imgSrc
        });
    });
    return R;
}"""

def scrape_bigbasket(query, lat=None, lng=None):
    try:
        with sync_playwright() as p:
            browser, ctx = _make_ctx(p, lat=lat, lng=lng)
            page = ctx.new_page()
            products = []
            try:
                url = f"https://www.bigbasket.com/ps/?q={query.replace(' ','+')}&nc=as"
                page.goto(url, wait_until='domcontentloaded', timeout=45000)
                try: page.wait_for_load_state('networkidle', timeout=12000)
                except: pass
                # Wait for product cards to load dynamically
                try: page.wait_for_selector('li.PaginateItems___StyledLi, [class*="SKUCard"], [class*="sku-card"]', timeout=8000)
                except: pass
                for i in range(1, 4):
                    page.evaluate(f"window.scrollTo(0,{i*600})")
                    time.sleep(0.4)
                raw = page.evaluate(_BB_JS)
                log.info(f"[BigBasket] DOM returned {len(raw)} items")
                seen = set()
                for it in raw:
                    name = (it.get('name') or '').strip()
                    price = float(it.get('price') or 0)
                    if not name or price <= 0: continue
                    key = f"{name.lower()[:30]}_{price}"
                    if key in seen: continue
                    seen.add(key)
                    products.append({
                        'source':'BigBasket','name':name,'price':price,
                        'mrp':max(float(it.get('mrp') or price),price),
                        'quantity':it.get('quantity',''),'link':it.get('link',''),
                        'image':it.get('image',''),'rating':float(it.get('rating') or 0),
                    })
            finally:
                page.close(); ctx.close(); browser.close()
        log.info(f"[BigBasket] Returning {len(products)} products")
        return products[:10]
    except Exception as e:
        log.error(f"[BigBasket] Fatal: {e}"); return []


def scrape_blinkit(query, lat=None, lng=None):
    api_patterns = [
        'blinkit.com/v2/', 'blinkit.com/v3/', 'blinkit.com/api/',
        '/product/search', '/products/search', 'api.blinkit.com', 'layout/search',
    ]
    url = f"https://blinkit.com/s/?q={query.replace(' ','+')}"
    return _scrape_with_intercept(
        'Blinkit', url, api_patterns, _parse_blinkit_api, _BLINKIT_JS,
        wait_sel="div[id]", limit=10, lat=lat, lng=lng
    )

def scrape_instamart(query, lat=None, lng=None, city=None):
    import json
    import urllib.parse
    url = f"https://www.swiggy.com/instamart/search?query={query.replace(' ','%20')}"
    
    _setup = None
    if lat is not None and lng is not None:
        latitude = lat
        longitude = lng
        city_name = city if city is not None else "Bangalore"
        
        # Construct userLocation cookie value
        user_loc_obj = {
            "lat": latitude,
            "lng": longitude,
            "address": f"{city_name}, India",
            "id": "",
            "annotation": f"{city_name}, India",
            "name": ""
        }
        user_loc_val = urllib.parse.quote(json.dumps(user_loc_obj))
        
        def _setup_fn(ctx):
            ctx.add_cookies([
                {"name":"lat","value":str(latitude),"domain":".swiggy.com","path":"/"},
                {"name":"lng","value":str(longitude),"domain":".swiggy.com","path":"/"},
                {"name":"cityName","value":str(city_name),"domain":".swiggy.com","path":"/"},
                {"name":"userLocation","value":user_loc_val,"domain":".swiggy.com","path":"/"},
                {"name":"lat","value":str(latitude),"domain":"www.swiggy.com","path":"/"},
                {"name":"lng","value":str(longitude),"domain":"www.swiggy.com","path":"/"},
                {"name":"cityName","value":str(city_name),"domain":"www.swiggy.com","path":"/"},
                {"name":"userLocation","value":user_loc_val,"domain":"www.swiggy.com","path":"/"},
            ])
        _setup = _setup_fn
        
    api_patterns = ['swiggy.com/api','api.swiggy.com','/instamart/search','/msa-listing']
    storage_state = "instamart_state.json"
    
    return _scrape_with_intercept(
        'Instamart', url, api_patterns, _parse_instamart_api, _INSTAMART_JS,
        setup_fn=_setup,
        wait_sel="[class*='ItemCard'],[class*='itemCard']",
        limit=10, lat=lat, lng=lng, storage_state=storage_state
    )

def get_scraped_products(query: str, lat=None, lng=None, city=None) -> list:
    log.info(f"Parallel scrape for: '{query}' with location: {city} ({lat}, {lng})")
    all_products = []
    scrapers = {
        "BigBasket": lambda q: scrape_bigbasket(q, lat=lat, lng=lng),
        "Blinkit": lambda q: scrape_blinkit(q, lat=lat, lng=lng),
        "Zepto": lambda q: scrape_zepto(q, lat=lat, lng=lng),
        "Instamart": lambda q: scrape_instamart(q, lat=lat, lng=lng, city=city)
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(fn, query): name for name, fn in scrapers.items()}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result = future.result(timeout=120)
                log.info(f"[{name}] done: {len(result)} products")
                all_products.extend(result)
            except concurrent.futures.TimeoutError:
                log.warning(f"[{name}] timed out")
            except Exception as exc:
                log.error(f"[{name}] error: {exc}")
    log.info(f"Total products: {len(all_products)}")
    import gc
    gc.collect()
    return all_products

if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    for p in get_scraped_products("rice"):
        print(f"[{p['source']}] {p['name'][:50]} | Rs.{p['price']} | MRP Rs.{p['mrp']} | {p['quantity']}")
