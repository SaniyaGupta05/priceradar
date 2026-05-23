"""
PriceRadar — Production-ready Flask application.
Fixes applied:
  1. WinError 10038 (Windows socket crash) — disabled Werkzeug reloader;
     use 'python run.py' for development; Waitress for production.
  2. API key moved to .env (python-dotenv).
  3. Improved cache clear endpoint.
  4. Health check / status endpoint.
"""

import os
import re
import time
import json
import hashlib
import requests
import threading
from urllib.parse import quote
from difflib import SequenceMatcher

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
from scraper import get_scraped_products
import logging

# ── Load environment variables ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; env vars must be set manually

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = Flask(__name__)
frontend_url = os.environ.get("FRONTEND_URL", "*")
CORS(app, resources={r"/*": {"origins": frontend_url}})

# ── Config ─────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
CACHE_TTL    = int(os.environ.get("CACHE_TTL", 600))   # seconds

if not GROQ_API_KEY:
    log.warning("GROQ_API_KEY is not set — AI analysis will be disabled.")

# ── In-memory cache (thread-safe) ──────────────────────────────────────────
_cache: dict       = {}
_cache_lock        = threading.Lock()


def resolve_pincode(pincode: str) -> tuple[float, float, str]:
    """
    Resolves a 6-digit Indian pincode to coordinates (latitude, longitude, cityName).
    """
    pincode = re.sub(r'\D', '', pincode).strip()
    if len(pincode) != 6:
        return 12.9716, 77.5946, "Bangalore"  # Default fallback
        
    major_cities = {
        "560001": (12.9716, 77.5946, "Bangalore"),
        "110001": (28.6333, 77.2167, "Delhi"),
        "400001": (18.9219, 72.8344, "Mumbai"),
        "700001": (22.5626, 88.3510, "Kolkata"),
        "600001": (13.0827, 80.2707, "Chennai"),
        "500001": (17.3850, 78.4867, "Hyderabad"),
        "411001": (18.5204, 73.8567, "Pune"),
        "122001": (28.4595, 77.0266, "Gurgaon"),
        "201301": (28.5355, 77.3910, "Noida"),
        "380001": (23.0225, 72.5714, "Ahmedabad"),
    }
    
    if pincode.startswith("390"):
        return 22.3072, 73.1812, "Vadodara"

    if pincode in major_cities:
        return major_cities[pincode]
        
    try:
        url = f"https://api.zippopotam.us/IN/{pincode}"
        resp = requests.get(url, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if "places" in data and len(data["places"]) > 0:
                place = data["places"][0]
                lat = float(place.get("latitude", 12.9716))
                lng = float(place.get("longitude", 77.5946))
                city = place.get("place name", "Unknown City")
                if not city or city == "Unknown City":
                    city = place.get("state", "India")
                if "vadodara" in city.lower() or "baroda" in city.lower():
                    return 22.3072, 73.1812, city
                return lat, lng, city
    except Exception as e:
        log.warning(f"Error resolving pincode {pincode} via Zippopotam: {e}")
        
    zone_fallbacks = {
        "1": (28.6333, 77.2167, "Delhi Region"),
        "2": (28.5355, 77.3910, "Noida/UP Region"),
        "3": (23.0225, 72.5714, "Gujarat/Rajasthan"),
        "4": (18.9219, 72.8344, "Mumbai Region"),
        "5": (12.9716, 77.5946, "Bangalore Region"),
        "6": (13.0827, 80.2707, "Chennai Region"),
        "7": (22.5626, 88.3510, "Kolkata Region"),
        "8": (25.5941, 85.1376, "Patna Region"),
    }
    first_digit = pincode[0]
    if first_digit in zone_fallbacks:
        return zone_fallbacks[first_digit]
        
    return 12.9716, 77.5946, "Bangalore"  # Default


def _cache_key(query: str, pincode: str = "560001") -> str:
    key_str = f"{query.lower().strip()}_{pincode.strip()}"
    return hashlib.md5(key_str.encode()).hexdigest()


def _cache_get(query: str, pincode: str = "560001"):
    key = _cache_key(query, pincode)
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry["ts"]) < CACHE_TTL:
            log.info(f"Cache HIT for '{query}' (pincode: {pincode})")
            return entry["data"]
    return None


def _cache_set(query: str, data, pincode: str = "560001"):
    key = _cache_key(query, pincode)
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}


# ── Utility helpers ─────────────────────────────────────────────────────────

def normalize_quantity(q: str) -> str:
    if not q:
        return ""
    q_lower = q.lower().strip()
    
    # 1. Try to find a compound/multi-pack pattern like "10 x 10 g" or "10x10 g"
    multipack_match = re.search(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(g|kg|l|ml|gm|gms|pc|pcs|unit|units)\b", q_lower)
    if multipack_match:
        val1 = multipack_match.group(1)
        val2 = multipack_match.group(2)
        unit = multipack_match.group(3)
        unit = unit.replace("gms", "g").replace("gm", "g").replace("pcs", "pc").replace("units", "pc")
        return f"{val1}x{val2}{unit}"

    # 2. Try to find a weight/volume pattern like "100 g" or "1 kg"
    weight_match = re.search(r"(\d+(?:\.\d+)?)\s*(g|kg|l|ml|gm|gms|ltr|liter|litre)\b", q_lower)
    if weight_match:
        val = weight_match.group(1)
        unit = weight_match.group(2)
        unit = unit.replace("ltr", "l").replace("liter", "l").replace("litre", "l")
        unit = unit.replace("gms", "g").replace("gm", "g")
        unit = unit.replace("kgs", "kg")
        return f"{val}{unit}"
        
    # 3. Try to find other units like pc, pcs, unit, units, piece, pack
    count_match = re.search(r"(\d+(?:\.\d+)?)\s*(pc|pcs|unit|units|piece|pack|packet)\b", q_lower)
    if count_match:
        val = count_match.group(1)
        unit = count_match.group(2)
        unit = unit.replace("pcs", "pc").replace("pieces", "pc").replace("piece", "pc")
        unit = unit.replace("units", "pc").replace("unit", "pc")
        unit = unit.replace("packet", "pack")
        return f"{val}{unit}"
        
    # Fallback to the original logic
    q = q_lower.replace(" ", "")
    q = q.replace("ltr", "l").replace("liter", "l").replace("litre", "l")
    q = q.replace("gms", "g").replace("gm", "g")
    q = q.replace("kgs", "kg")
    q = q.replace("pcs", "pc").replace("pieces", "pc").replace("unit", "pc")
    return q



def get_quantity_from_string(s: str) -> str:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(g|kg|l|ml|pc|pcs|unit|units|gm|gms|ltr|liter|litre|pack|piece)\b",
        s.lower(),
    )
    return f"{match.group(1)}{match.group(2)}" if match else ""


def calculate_unit_price(price: float, quantity_str: str) -> float:
    if not quantity_str or price <= 0:
        return price
    q = quantity_str.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|l|ml|pc|gm|gms)\b", q)
    if not match:
        return price
    val  = float(match.group(1))
    unit = match.group(2)
    if val <= 0:
        return price
    if unit in ("kg", "l"):
        return price / val
    if unit in ("g", "gm", "gms", "ml"):
        return (price / val) * 1000
    return price / val


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _conflict_variants(a: str, b: str) -> bool:
    variants = [
        "tomato", "chicken", "masala", "atta", "oats", "cheese", "chocolate",
        "vanilla", "strawberry", "mango", "magic", "double", "cuppa",
        "yippee", "top ramen", "knorr", "tata", "amul", "nestle",
    ]
    for v in variants:
        if (v in a and v not in b) or (v not in a and v in b):
            return True
    return False


def group_products(products: list) -> list:
    """Group similar products across platforms for side-by-side comparison."""
    groups = []
    for p in products:
        p_name = p["name"].lower()
        p_qty  = normalize_quantity(p.get("quantity", "")) or normalize_quantity(
            get_quantity_from_string(p["name"])
        )
        matched = False
        for group in groups:
            rep      = group["products"][0]
            rep_name = rep["name"].lower()
            rep_qty  = normalize_quantity(rep.get("quantity", "")) or normalize_quantity(
                get_quantity_from_string(rep["name"])
            )

            if p_qty and rep_qty and p_qty != rep_qty:
                continue

            p_brand = p_name.split()[0] if p_name else ""
            r_brand = rep_name.split()[0] if rep_name else ""
            if p_brand and r_brand and p_brand != r_brand:
                continue

            if _conflict_variants(p_name, rep_name):
                continue

            score = similar(p_name, rep_name)
            if score > 0.58:
                existing_idx = next(
                    (i for i, ep in enumerate(group["products"]) if ep["source"] == p["source"]), -1
                )
                if existing_idx != -1:
                    if p["price"] < group["products"][existing_idx]["price"]:
                        group["products"][existing_idx] = p
                        if p.get("image") and not group.get("image"):
                            group["image"] = p["image"]
                else:
                    group["products"].append(p)
                    if not group.get("image") and p.get("image"):
                        group["image"] = p["image"]
                matched = True
                break

        if not matched:
            groups.append({
                "name":     p["name"],
                "image":    p.get("image", ""),
                "quantity": p_qty,
                "products": [p],
            })

    groups.sort(key=lambda g: (-len(g["products"]), g["products"][0]["price"]))
    return groups


def compare_and_select_best(all_products: list, query: str = "", top_n: int = 20) -> list:
    """Deduplicate, score, and rank products."""
    if not all_products:
        return []

    seen   = set()
    unique = []
    for p in all_products:
        qty_str        = p.get("quantity") or get_quantity_from_string(p["name"])
        p["unit_price"]    = calculate_unit_price(p["price"], qty_str)
        p["extracted_qty"] = qty_str
        key = f"{p['name'].lower().strip()}_{p['price']}_{p['source']}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    for p in unique:
        rating = p.get("rating") or 3.5
        base   = p["price"] / max(rating, 0.1)
        penalty = 1.0
        if query:
            q_words = set(re.findall(r"\w+", query.lower()))
            n_words = set(re.findall(r"\w+", p["name"].lower()))
            matched = sum(
                1 for qw in q_words
                if any(qw in nw or nw in qw for nw in n_words) and len(qw) > 2
            )
            if matched == 0:
                penalty = 15.0
            elif matched < len(q_words):
                penalty = 2.5
        p["composite_score"] = base * penalty

    return sorted(unique, key=lambda x: x.get("composite_score", x["price"]))[:top_n]


# ── AI Analysis via Groq ────────────────────────────────────────────────────
def analyze_products_with_ai(products: list, query: str) -> str:
    if not products:
        return "<p>No products found to analyze.</p>"

    if not GROQ_API_KEY:
        return "<p>⚠️ AI analysis unavailable — GROQ_API_KEY not configured.</p>"

    try:
        product_info = "\n".join([
            f"{i+1}. {p['name']} — ₹{p['price']} ({p['source']}) {p.get('quantity','')}"
            for i, p in enumerate(products[:8])
        ])

        prompt = f"""You are a helpful Indian shopping assistant. The user searched for "{query}".

Here are prices found across Blinkit, BigBasket, Zepto, and Swiggy Instamart:
{product_info}

Write a SHORT, friendly, HTML-formatted shopping advice (no markdown, no code blocks).
Rules:
- Use ONLY these HTML tags: <h3>, <p>, <ul>, <li>, <strong>, <span>
- Start with <h3>🏆 Best Pick</h3> — name the cheapest option and platform in 1 sentence.
- Then <h3>⚖️ Price Snapshot</h3> with a <ul> of 2-3 notable comparisons (mention platform names).
- End with <h3>💡 Tip</h3> — a quick 1-sentence buying tip.
- Be conversational. Use rupee symbol ₹. No markdown. No generic advice.
"""

        resp = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "messages":   [{"role": "user", "content": prompt}],
                "model":      "llama-3.1-8b-instant",
                "max_tokens": 600,
                "temperature": 0.65,
            },
            timeout=25,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    except requests.HTTPError as e:
        code = e.response.status_code
        if code == 401:
            return "<p>⚠️ AI key invalid. Please update GROQ_API_KEY in your .env file.</p>"
        if code == 429:
            return "<p>⚠️ AI rate limit hit. Try again in a moment.</p>"
        return f"<p>⚠️ AI unavailable (HTTP {code}).</p>"
    except Exception as e:
        log.error(f"AI Error: {e}")
        return "<p>⚠️ AI analysis unavailable. Compare prices above!</p>"


# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    pincode = request.args.get("pincode", "").strip()
    if not pincode:
        pincode = request.cookies.get("pincode", "560001").strip()
    if not re.match(r'^\d{6}$', pincode):
        pincode = "560001"
    lat, lng, city = resolve_pincode(pincode)
    
    resp = render_template("index.html", pincode=pincode, resolved_city=city)
    from flask import make_response
    response_obj = make_response(resp)
    response_obj.set_cookie("pincode", pincode, max_age=30*24*60*60)
    return response_obj


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return redirect(url_for("index"))

    pincode = request.args.get("pincode", "").strip()
    if not pincode:
        pincode = request.cookies.get("pincode", "560001").strip()
    if not re.match(r'^\d{6}$', pincode):
        pincode = "560001"

    lat, lng, city = resolve_pincode(pincode)
    log.info(f"Search for '{query}' with resolved location: {city} ({lat}, {lng})")

    # Cache check
    cached = _cache_get(query, pincode)
    if cached:
        resp = render_template(
            "search.html",
            query=query,
            pincode=pincode,
            resolved_city=city,
            products=cached["products"],
            grouped_products=cached["grouped"],
            best_deal=cached["best_deal"],
            savings=cached["savings"],
            source_stats=cached["source_stats"],
            from_cache=True,
        )
        from flask import make_response
        response_obj = make_response(resp)
        response_obj.set_cookie("pincode", pincode, max_age=30*24*60*60)
        return response_obj

    log.info(f"Live scraping: '{query}' for pincode {pincode}")
    all_products = get_scraped_products(query, lat=lat, lng=lng, city=city)

    if not all_products:
        resp = render_template(
            "search.html",
            query=query,
            pincode=pincode,
            resolved_city=city,
            products=[],
            grouped_products=[],
            best_deal=None,
            savings=0,
            source_stats={},
            from_cache=False,
        )
        from flask import make_response
        response_obj = make_response(resp)
        response_obj.set_cookie("pincode", pincode, max_age=30*24*60*60)
        return response_obj

    best_products = compare_and_select_best(all_products, query)
    grouped       = group_products(best_products)
    best_deal     = best_products[0] if best_products else None
    savings       = max(0, (best_deal.get("mrp", 0) or 0) - best_deal["price"]) if best_deal else 0

    source_stats: dict = {}
    for p in all_products:
        src = p["source"]
        source_stats.setdefault(src, {"count": 0, "min_price": float("inf")})
        source_stats[src]["count"]     += 1
        source_stats[src]["min_price"] = min(source_stats[src]["min_price"], p["price"])
    for src in source_stats:
        if source_stats[src]["min_price"] == float("inf"):
            source_stats[src]["min_price"] = 0

    payload = {
        "products":     best_products,
        "grouped":      grouped,
        "best_deal":    best_deal,
        "savings":      savings,
        "source_stats": source_stats,
    }
    _cache_set(query, payload, pincode)

    resp = render_template(
        "search.html",
        query=query,
        pincode=pincode,
        resolved_city=city,
        products=best_products,
        grouped_products=grouped,
        best_deal=best_deal,
        savings=savings,
        source_stats=source_stats,
        from_cache=False,
    )
    from flask import make_response
    response_obj = make_response(resp)
    response_obj.set_cookie("pincode", pincode, max_age=30*24*60*60)
    return response_obj


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    pincode = request.args.get("pincode", "").strip()
    if not pincode:
        pincode = request.cookies.get("pincode", "560001").strip()
    if not re.match(r'^\d{6}$', pincode):
        pincode = "560001"

    lat, lng, city = resolve_pincode(pincode)
    log.info(f"[API Search] for '{query}' with resolved location: {city} ({lat}, {lng})")

    # Cache check
    cached = _cache_get(query, pincode)
    if cached:
        return jsonify({
            "query": query,
            "pincode": pincode,
            "resolved_city": city,
            "products": cached["products"],
            "grouped_products": cached["grouped"],
            "best_deal": cached["best_deal"],
            "savings": cached["savings"],
            "source_stats": cached["source_stats"],
            "from_cache": True
        })

    log.info(f"[API Search] Live scraping: '{query}' for pincode {pincode}")
    all_products = get_scraped_products(query, lat=lat, lng=lng, city=city)

    if not all_products:
        return jsonify({
            "query": query,
            "pincode": pincode,
            "resolved_city": city,
            "products": [],
            "grouped_products": [],
            "best_deal": None,
            "savings": 0,
            "source_stats": {},
            "from_cache": False
        })

    best_products = compare_and_select_best(all_products, query)
    grouped       = group_products(best_products)
    best_deal     = best_products[0] if best_products else None
    savings       = max(0, (best_deal.get("mrp", 0) or 0) - best_deal["price"]) if best_deal else 0

    source_stats: dict = {}
    for p in all_products:
        src = p["source"]
        source_stats.setdefault(src, {"count": 0, "min_price": float("inf")})
        source_stats[src]["count"]     += 1
        source_stats[src]["min_price"] = min(source_stats[src]["min_price"], p["price"])
    for src in source_stats:
        if source_stats[src]["min_price"] == float("inf"):
            source_stats[src]["min_price"] = 0

    payload = {
        "products":     best_products,
        "grouped":      grouped,
        "best_deal":    best_deal,
        "savings":      savings,
        "source_stats": source_stats,
    }
    _cache_set(query, payload, pincode)

    return jsonify({
        "query": query,
        "pincode": pincode,
        "resolved_city": city,
        "products": best_products,
        "grouped_products": grouped,
        "best_deal": best_deal,
        "savings": savings,
        "source_stats": source_stats,
        "from_cache": False
    })


@app.route("/api/ai_analysis", methods=["POST"])
def ai_analysis():
    data     = request.json or {}
    products = data.get("products", [])
    query    = data.get("query", "")
    return jsonify({"analysis": analyze_products_with_ai(products, query)})


@app.route("/about")
def about():
    pincode = request.cookies.get("pincode", "560001").strip()
    if not re.match(r'^\d{6}$', pincode):
        pincode = "560001"
    lat, lng, city = resolve_pincode(pincode)
    return render_template("about.html", pincode=pincode, resolved_city=city)


@app.route("/api/sources")
def api_sources():
    """Health check — lists active scrapers and cache size."""
    with _cache_lock:
        cache_size = len(_cache)
    return jsonify({
        "sources": ["Blinkit", "BigBasket", "Zepto", "Instamart"],
        "status":  "operational",
        "cache_entries": cache_size,
    })


@app.route("/api/cache/clear", methods=["GET", "POST"])
def api_cache_clear():
    """Clear in-memory cache (admin/developer use)."""
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
    log.info(f"Cache cleared — {count} entries removed.")
    return jsonify({
        "cleared": count,
        "status": "ok",
        "message": "Cache cleared successfully! You can now perform fresh searches."
    })


@app.route("/api/zepto-product", methods=["GET"])
def api_zepto_product():
    """
    Scrape Zepto for a single product and return its direct product URL.

    Query params:
      name  (required) — product name to search, e.g. "Amul Butter 500g"

    Response (200):
      {
        "product_name":       "Amul Butter",
        "direct_product_url": "https://www.zeptonow.com/pn/amul-butter/pvid/xxxxx",
        "price":              "₹56",
        "pack_size":          "100 g"
      }

    Response (400): missing name param
    Response (404): no product found / only search-URL fallbacks returned
    Response (500): scraper error
    """
    from scraper import scrape_zepto

    name = request.args.get("name", "").strip()
    if not name:
        return jsonify({"error": "Missing required query param: name"}), 400

    pincode = request.args.get("pincode", "").strip()
    if not pincode:
        pincode = request.cookies.get("pincode", "560001").strip()
    if not re.match(r'^\d{6}$', pincode):
        pincode = "560001"

    # Resolve pincode to coordinates
    lat, lng, city = resolve_pincode(pincode)

    # Check cache first (reuse /search cache if it exists)
    cache_key_name = f"__zepto_product__{name.lower()}"
    cached = _cache_get(cache_key_name, pincode)
    if cached:
        return jsonify(cached)

    log.info(f"[/api/zepto-product] Scraping Zepto for: '{name}' in {city} ({pincode})")
    try:
        results = scrape_zepto(name, lat=lat, lng=lng)
    except Exception as exc:
        log.error(f"[/api/zepto-product] Scraper error: {exc}")
        return jsonify({"error": "Scraper encountered an error", "detail": str(exc)}), 500

    if not results:
        return jsonify({"error": "Product not found on Zepto"}), 404

    # Prefer entries with a direct /pn/ link; fall back to first result
    direct = [p for p in results if "/pn/" in p.get("link", "")]
    best   = direct[0] if direct else results[0]

    # If even the best result has no direct link, tell the caller
    if "/pn/" not in best.get("link", ""):
        return jsonify({
            "error":   "Could not obtain a direct product URL (only search fallback available)",
            "product_name": best["name"],
            "search_url":   best.get("link", ""),
            "price":        f"₹{best['price']:.0f}",
            "pack_size":    best.get("quantity", ""),
        }), 404

    payload = {
        "product_name":       best["name"],
        "direct_product_url": best["link"],
        "price":              f"₹{best['price']:.0f}",
        "pack_size":          best.get("quantity", ""),
    }

    # Cache so repeated calls are instant
    _cache_set(cache_key_name, payload, pincode)

    log.info(f"[/api/zepto-product] Returning: {payload}")
    return jsonify(payload)


# ── Entry point ─────────────────────────────────────────────────────────────
# IMPORTANT (Windows / WinError 10038):
#   Do NOT use app.run(debug=True) with use_reloader=True on Windows.
#   The Werkzeug stat-based reloader closes sockets in a way that breaks
#   the Windows socket selector on reload, raising OSError [WinError 10038].
#
#   • Development  → use run.py (launches with use_reloader=False)
#   • Production   → use waitress-serve (see run.py)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # use_reloader=False is the critical fix for WinError 10038 on Windows
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,      # set True only if you need Jinja/template reload
        use_reloader=False,  # ← FIX: prevents WinError 10038 on Windows
        threaded=True,
    )
