import { useState, useEffect } from 'react'
import { 
  Search, 
  MapPin, 
  TrendingUp, 
  Sparkles, 
  Loader2, 
  ExternalLink, 
  ShoppingBag, 
  Check, 
  Percent, 
  ArrowRight,
  RefreshCw,
  Info,
  ChevronRight,
  Filter,
  CheckCircle2,
  DollarSign
} from 'lucide-react'

function App() {
  const [query, setQuery] = useState('')
  const [pincode, setPincode] = useState('560001')
  const [resolvedCity, setResolvedCity] = useState('Bangalore')
  const [isEditingPincode, setIsEditingPincode] = useState(false)
  const [tempPincode, setTempPincode] = useState('560001')
  
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [error, setError] = useState(null)
  
  const [results, setResults] = useState(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState('')
  
  const [activeTab, setActiveTab] = useState('grouped') // 'grouped' | 'all'
  const [sortBy, setSortBy] = useState('price') // 'price' | 'unit_price' | 'score'
  const [selectedStore, setSelectedStore] = useState('all') // 'all' | 'Blinkit' | 'Zepto' | 'BigBasket' | 'Instamart'

  // Sync temp pincode
  useEffect(() => {
    const savedPincode = localStorage.getItem('pincode') || '560001'
    setPincode(savedPincode)
    setTempPincode(savedPincode)
    resolveCityName(savedPincode)
  }, [])

  const resolveCityName = async (pin) => {
    try {
      const majorCities = {
        "560001": "Bangalore",
        "110001": "Delhi",
        "400001": "Mumbai",
        "700001": "Kolkata",
        "600001": "Chennai",
        "500001": "Hyderabad",
        "411001": "Pune",
        "122001": "Gurgaon",
        "201301": "Noida",
        "380001": "Ahmedabad",
      }
      if (majorCities[pin]) {
        setResolvedCity(majorCities[pin])
        return
      }
      const res = await fetch(`https://api.zippopotam.us/IN/${pin}`)
      if (res.ok) {
        const data = await res.json()
        if (data.places && data.places.length > 0) {
          setResolvedCity(data.places[0]['place name'] || 'India')
        }
      }
    } catch (e) {
      // Fallback
    }
  }

  const handlePincodeSubmit = (e) => {
    e.preventDefault()
    if (/^\d{6}$/.test(tempPincode)) {
      setPincode(tempPincode)
      localStorage.setItem('pincode', tempPincode)
      resolveCityName(tempPincode)
      setIsEditingPincode(false)
    } else {
      alert('Please enter a valid 6-digit Indian pincode')
    }
  }

  const handleSearch = async (e, searchQ = query) => {
    if (e) e.preventDefault()
    if (!searchQ.trim()) return

    setQuery(searchQ)
    setLoading(true)
    setError(null)
    setResults(null)
    setAiAnalysis('')
    
    // Animate loader text
    const statusSteps = [
      'Scanning grocery stores in real-time...',
      'Connecting to Swiggy Instamart...',
      'Querying Blinkit catalog...',
      'Fetching Zepto stock...',
      'Reading BigBasket prices...',
      'Ranking and grouping products...'
    ]
    let stepIdx = 0
    setStatusMessage(statusSteps[0])
    const interval = setInterval(() => {
      stepIdx = (stepIdx + 1) % statusSteps.length
      setStatusMessage(statusSteps[stepIdx])
    }, 2000)

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(searchQ)}&pincode=${pincode}`)
      clearInterval(interval)
      
      if (!res.ok) {
        throw new Error('API server returned an error. Please try again.')
      }
      
      const data = await res.json()
      if (data.error) {
        throw new Error(data.error)
      }

      setResults(data)
      if (data.resolved_city) {
        setResolvedCity(data.resolved_city)
      }

      // Fetch AI analysis
      if (data.products && data.products.length > 0) {
        triggerAiAnalysis(data.products, searchQ)
      }
    } catch (err) {
      clearInterval(interval)
      setError(err.message || 'Scrapers timed out or failed. Please try a different search.')
    } finally {
      setLoading(false)
    }
  }

  const triggerAiAnalysis = async (products, searchQ) => {
    setAiLoading(true)
    try {
      const res = await fetch('/api/ai_analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ products, query: searchQ })
      })
      if (res.ok) {
        const data = await res.json()
        setAiAnalysis(data.analysis)
      } else {
        setAiAnalysis('<h3>AI Advice</h3><p>Could not generate AI summary at this moment. Please compare the store prices below.</p>')
      }
    } catch (err) {
      setAiAnalysis('<h3>AI Advice</h3><p>Could not connect to AI advisor. Please compare the store prices below.</p>')
    } finally {
      setAiLoading(false)
    }
  }

  const resetSearch = () => {
    setResults(null)
    setQuery('')
    setAiAnalysis('')
  }

  const handleGetStarted = () => {
    resetSearch()
    setTimeout(() => {
      const searchInput = document.getElementById('hero-search-input')
      if (searchInput) {
        searchInput.focus()
        searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 50)
  }

  const handleHomeClick = (e) => {
    if (e) e.preventDefault()
    resetSearch()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleHowItWorksClick = (e) => {
    e.preventDefault()
    resetSearch()
    setTimeout(() => {
      const el = document.getElementById('how-it-works')
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 100)
  }

  const handleFeaturesClick = (e) => {
    e.preventDefault()
    resetSearch()
    setTimeout(() => {
      const el = document.getElementById('features')
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 100)
  }

  // Helper to format source tags
  const getStoreBadgeColor = (store) => {
    switch (store.toLowerCase()) {
      case 'blinkit': return 'bg-amber-100 text-amber-800 border-amber-200'
      case 'zepto': return 'bg-purple-100 text-purple-800 border-purple-200'
      case 'instamart': return 'bg-orange-100 text-orange-800 border-orange-200'
      case 'bigbasket': return 'bg-emerald-100 text-emerald-800 border-emerald-200'
      default: return 'bg-slate-100 text-slate-800 border-slate-200'
    }
  }

  // Filter & Sort Products
  const getSortedProducts = () => {
    if (!results || !results.products) return []
    let list = [...results.products]
    
    // Store Filter
    if (selectedStore !== 'all') {
      list = list.filter(p => p.source.toLowerCase() === selectedStore.toLowerCase())
    }

    // Sorting
    list.sort((a, b) => {
      if (sortBy === 'price') return a.price - b.price
      if (sortBy === 'unit_price') return (a.unit_price || a.price) - (b.unit_price || b.price)
      if (sortBy === 'score') return (a.composite_score || 0) - (b.composite_score || 0)
      return 0
    })

    return list
  }

  return (
    <div className="min-h-screen flex flex-col font-sans bg-[#fcfcfb]">
      {/* Navigation Header */}
      <header className="sticky top-0 z-40 w-full bg-white/80 backdrop-blur-md border-b border-slate-100 px-6 py-4 shadow-xs">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2 cursor-pointer" onClick={resetSearch}>
            <div className="bg-[#10b981] p-2 rounded-xl text-white shadow-xs">
              <ShoppingBag className="w-6 h-6" />
            </div>
            <span className="font-display font-extrabold text-2xl tracking-tight text-[#0f172a] flex items-center gap-1">
              ShopSmart<span className="text-[#10b981]">AI</span>
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-semibold text-slate-600">
            <button onClick={handleHomeClick} className="hover:text-[#10b981] transition-colors">Home</button>
            <a href="#how-it-works" onClick={handleHowItWorksClick} className="hover:text-[#10b981] transition-colors">How It Works</a>
            <a href="#features" onClick={handleFeaturesClick} className="hover:text-[#10b981] transition-colors">Features</a>
          </nav>

          <div className="flex items-center gap-4">
            {/* Pincode Widget */}
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-100 px-3 py-1.5 rounded-full text-xs font-semibold text-slate-700">
              <MapPin className="w-3.5 h-3.5 text-[#10b981]" />
              {isEditingPincode ? (
                <form onSubmit={handlePincodeSubmit} className="flex items-center gap-1">
                  <input 
                    type="text" 
                    value={tempPincode}
                    onChange={(e) => setTempPincode(e.target.value)}
                    className="w-16 bg-white border border-slate-200 rounded px-1 text-center font-bold text-slate-800 outline-none"
                    maxLength={6}
                    autoFocus
                  />
                  <button type="submit" className="text-[#10b981] hover:underline font-bold">Save</button>
                </form>
              ) : (
                <span className="cursor-pointer flex items-center gap-1 hover:text-[#10b981]" onClick={() => setIsEditingPincode(true)}>
                  {resolvedCity} ({pincode})
                  <span className="text-[10px] text-slate-400 font-normal">(change)</span>
                </span>
              )}
            </div>

            <button 
              onClick={handleGetStarted}
              className="bg-[#10b981] text-white text-sm font-bold px-4 py-2 rounded-full hover:bg-[#0d9668] transition-colors shadow-xs"
            >
              Get Started
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8">
        
        {/* LANDING PAGE STATE */}
        {!results && !loading && (
          <div className="flex flex-col gap-16 py-12 md:py-20">
            
            {/* Hero Banner */}
            <div className="grid md:grid-cols-12 gap-12 items-center">
              <div className="md:col-span-7 flex flex-col gap-6 text-left">
                <div className="inline-flex items-center gap-1.5 bg-[#e6f7f0] border border-[#a3e635]/20 text-[#0f9f6e] px-4 py-1.5 rounded-full text-xs font-bold w-fit tracking-wide uppercase">
                  <Sparkles className="w-3.5 h-3.5" /> AI-Powered Price Intelligence
                </div>
                
                <h1 className="font-display font-black text-5xl sm:text-6xl tracking-tight text-[#0f172a] leading-[1.05]">
                  Compare Grocery Prices <span className="bg-gradient-to-r from-[#10b981] to-[#34d399] bg-clip-text text-transparent">Instantly</span> with AI
                </h1>
                
                <p className="text-lg text-slate-500 leading-relaxed max-w-xl">
                  ShopSmartAI scans BigBasket, Blinkit, Zepto, and Instamart in real-time to find you the best deals. Save money, save time.
                </p>

                {/* Search Bar Component */}
                <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-3 max-w-2xl mt-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5" />
                    <input 
                      id="hero-search-input"
                      type="text"
                      placeholder="Search for groceries... (e.g., milk, bread, eggs)"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      className="w-full pl-12 pr-4 py-4 rounded-2xl bg-white border border-slate-200 text-slate-800 shadow-md placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#10b981]/50 focus:border-[#10b981] transition-all text-base"
                    />
                  </div>
                  <button 
                    type="submit"
                    className="bg-[#10b981] text-white font-bold px-8 py-4 rounded-2xl hover:bg-[#0d9668] transition-all hover:scale-[1.01] active:scale-[0.99] shadow-md flex items-center justify-center gap-2 text-base"
                  >
                    Compare Prices <ArrowRight className="w-4 h-4" />
                  </button>
                </form>

                {/* Quick Search Suggestions */}
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1">Popular:</span>
                  {['Milk', 'Lay\'s Chips', 'Amul Butter', 'Atta 5kg', 'Eggs', 'Coca Cola'].map((tag) => (
                    <button
                      key={tag}
                      onClick={(e) => handleSearch(e, tag)}
                      className="text-xs font-medium bg-slate-50 border border-slate-100 hover:border-slate-300 text-slate-600 px-3 py-1.5 rounded-full transition-all"
                    >
                      {tag}
                    </button>
                  ))}
                </div>

                {/* Bullets */}
                <div className="flex flex-wrap items-center gap-x-8 gap-y-3 mt-4 border-t border-slate-100 pt-6 text-sm text-slate-500 font-medium">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#10b981] animate-pulse"></span>
                    Live local prices
                  </div>
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#10b981]" />
                    AI recommendations
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-emerald-500 bg-emerald-50 rounded-full p-0.5" />
                    100% Free
                  </div>
                </div>
              </div>

              {/* Cartoon Interactive Illustration */}
              <div className="md:col-span-5 relative flex justify-center">
                <div className="w-full max-w-[400px] aspect-square rounded-3xl bg-gradient-to-tr from-[#e6f7f0] to-[#f4fbf8] p-8 flex flex-col justify-between shadow-lg relative overflow-hidden border border-emerald-50/50">
                  {/* Floating abstract rings */}
                  <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full bg-emerald-100/30"></div>
                  <div className="absolute -bottom-16 -left-16 w-48 h-48 rounded-full bg-[#10b981]/5"></div>

                  <div className="flex justify-between items-start z-10">
                    <div className="bg-white px-3 py-1.5 rounded-2xl shadow-xs border border-slate-100 flex items-center gap-1.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#10b981]"></div>
                      <span className="text-[10px] font-black text-slate-700">SCANNING ACTIVE</span>
                    </div>
                    <span className="text-xs font-semibold text-slate-400">Pincode: {pincode}</span>
                  </div>

                  {/* Mock store items showcasing price variation */}
                  <div className="flex flex-col gap-3 my-6 z-10">
                    <div className="bg-white p-3.5 rounded-2xl shadow-xs border border-slate-100 flex items-center justify-between hover:scale-[1.02] transition-transform">
                      <div className="flex items-center gap-2.5">
                        <span className="w-8 h-8 rounded-lg bg-orange-100 text-orange-700 flex items-center justify-center font-extrabold text-sm">I</span>
                        <div>
                          <p className="text-xs font-bold text-slate-800">Instamart</p>
                          <p className="text-[10px] text-slate-400">Delivery in 10m</p>
                        </div>
                      </div>
                      <span className="text-sm font-bold text-slate-800">₹145</span>
                    </div>

                    <div className="bg-white p-3.5 rounded-2xl shadow-md border-2 border-[#10b981] flex items-center justify-between hover:scale-[1.02] transition-transform relative">
                      <span className="absolute -top-2.5 right-4 bg-[#10b981] text-white text-[8px] font-extrabold px-2 py-0.5 rounded-full tracking-wider uppercase">Cheapest</span>
                      <div className="flex items-center gap-2.5">
                        <span className="w-8 h-8 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center font-extrabold text-sm">Z</span>
                        <div>
                          <p className="text-xs font-bold text-slate-800">Zepto</p>
                          <p className="text-[10px] text-slate-400">Delivery in 8m</p>
                        </div>
                      </div>
                      <span className="text-sm font-bold text-[#10b981]">₹128</span>
                    </div>

                    <div className="bg-white p-3.5 rounded-2xl shadow-xs border border-slate-100 flex items-center justify-between hover:scale-[1.02] transition-transform">
                      <div className="flex items-center gap-2.5">
                        <span className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-extrabold text-sm">B</span>
                        <div>
                          <p className="text-xs font-bold text-slate-800">Blinkit</p>
                          <p className="text-[10px] text-slate-400">Delivery in 12m</p>
                        </div>
                      </div>
                      <span className="text-sm font-bold text-slate-800">₹139</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between z-10 pt-2 border-t border-emerald-50">
                    <span className="text-xs font-bold text-emerald-800">Average Savings: 15% - 25%</span>
                    <Sparkles className="w-5 h-5 text-[#10b981] animate-bounce" />
                  </div>
                </div>
              </div>
            </div>

            {/* How It Works Section */}
            <section id="how-it-works" className="border-t border-slate-100 pt-16 flex flex-col gap-12 text-center">
              <div>
                <h2 className="font-display font-black text-3xl text-slate-900">Compare in 3 Easy Steps</h2>
                <p className="text-slate-500 mt-2">Saving money on daily essentials has never been this simple</p>
              </div>
              <div className="grid md:grid-cols-3 gap-8">
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-4 text-center">
                  <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#10b981] flex items-center justify-center font-extrabold text-lg">1</div>
                  <h3 className="font-bold text-slate-800 text-lg">Enter Pincode</h3>
                  <p className="text-sm text-slate-500">We use your pincode to fetch stock availability and accurate pricing from local dark stores near you.</p>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-4 text-center">
                  <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#10b981] flex items-center justify-center font-extrabold text-lg">2</div>
                  <h3 className="font-bold text-slate-800 text-lg">Search for Items</h3>
                  <p className="text-sm text-slate-500">Type any grocery product like Butter, Milk, or Maggi. We scrape all quick-commerce platforms in real-time.</p>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-4 text-center">
                  <div className="w-12 h-12 rounded-full bg-emerald-50 text-[#10b981] flex items-center justify-center font-extrabold text-lg">3</div>
                  <h3 className="font-bold text-slate-800 text-lg">See the Best Deal</h3>
                  <p className="text-sm text-slate-500">Our algorithm automatically matches packaging sizes and details. The AI recommends the best cart strategy!</p>
                </div>
              </div>
            </section>

            {/* Features Section */}
            <section id="features" className="border-t border-slate-100 pt-16 flex flex-col gap-12 text-center">
              <div>
                <h2 className="font-display font-black text-3xl text-slate-900">Powerful Features for Smarter Shopping</h2>
                <p className="text-slate-500 mt-2">ShopSmartAI utilizes advanced scraping and intelligence to give you the upper hand</p>
              </div>
              <div className="grid md:grid-cols-4 gap-6">
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-3 text-center">
                  <div className="bg-emerald-50 text-[#10b981] p-3 rounded-2xl">
                    <Search className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-slate-800 text-base">Real-time Scrape</h3>
                  <p className="text-xs text-slate-500">Scrapes Blinkit, BigBasket, Zepto, and Instamart instantly on-demand to guarantee live pricing.</p>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-3 text-center">
                  <div className="bg-purple-50 text-purple-600 p-3 rounded-2xl">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-slate-800 text-base">AI Shopping Assistant</h3>
                  <p className="text-xs text-slate-500">Llama-3 model evaluates deals, package weights, and recommends the absolute best buying strategy.</p>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-3 text-center">
                  <div className="bg-blue-50 text-blue-600 p-3 rounded-2xl">
                    <MapPin className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-slate-800 text-base">Location Targeting</h3>
                  <p className="text-xs text-slate-500">Resolves pincodes dynamically using geolocations, targeting your exact neighborhood dark store.</p>
                </div>
                <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-xs flex flex-col items-center gap-3 text-center">
                  <div className="bg-amber-50 text-amber-600 p-3 rounded-2xl">
                    <Percent className="w-6 h-6" />
                  </div>
                  <h3 className="font-bold text-slate-800 text-base">Side-by-Side Comparison</h3>
                  <p className="text-xs text-slate-500">Automatically groups similar items from different stores together for direct price and package matching.</p>
                </div>
              </div>
            </section>

          </div>
        )}

        {/* LOADING STATE */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 text-center gap-6 max-w-md mx-auto">
            <div className="relative">
              <div className="w-20 h-20 rounded-full border-4 border-slate-100 border-t-[#10b981] animate-spin"></div>
              <Sparkles className="w-8 h-8 text-[#10b981] absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 animate-pulse" />
            </div>
            
            <div className="space-y-2 mt-4">
              <h3 className="text-xl font-bold text-slate-800">Scraping Local Grocery Stores</h3>
              <p className="text-slate-500 text-sm font-semibold animate-pulse">{statusMessage}</p>
            </div>

            <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden mt-2">
              <div className="bg-[#10b981] h-full rounded-full animate-[loading_6s_ease-in-out_infinite]" style={{width: '60%'}}></div>
            </div>
            
            <p className="text-xs text-slate-400 italic">This usually takes about 5 to 12 seconds because we scan live inventories to avoid outdated pricing.</p>
          </div>
        )}

        {/* ERROR STATE */}
        {error && !loading && (
          <div className="flex flex-col items-center justify-center py-16 text-center max-w-lg mx-auto gap-4">
            <div className="bg-red-50 text-red-600 p-4 rounded-full">
              <Info className="w-12 h-12" />
            </div>
            <h3 className="text-xl font-bold text-slate-800">No results found</h3>
            <p className="text-slate-500 text-sm leading-relaxed">{error}</p>
            <div className="flex gap-4 mt-4">
              <button 
                onClick={() => handleSearch(null, query)} 
                className="bg-slate-800 text-white text-sm font-bold px-6 py-2.5 rounded-xl hover:bg-slate-900 flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" /> Retry
              </button>
              <button 
                onClick={resetSearch}
                className="border border-slate-200 text-slate-600 text-sm font-bold px-6 py-2.5 rounded-xl hover:bg-slate-50"
              >
                Go Home
              </button>
            </div>
          </div>
        )}

        {/* SEARCH RESULTS STATE */}
        {results && !loading && (
          <div className="flex flex-col gap-8">
            
            {/* Search Header Info */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-6">
              <div>
                <span className="text-xs font-extrabold text-[#10b981] uppercase tracking-wider">Search Results for</span>
                <h2 className="font-display font-black text-3xl text-slate-900 flex items-center gap-3">
                  "{results.query}"
                  <span className="text-sm font-medium text-slate-400 italic">in {results.resolved_city}</span>
                </h2>
              </div>
              
              {/* New Search Input inline */}
              <form onSubmit={handleSearch} className="flex gap-2 w-full md:w-auto max-w-md">
                <input 
                  type="text"
                  placeholder="Compare another item..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="px-4 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-[#10b981]/50 focus:border-[#10b981] w-full md:w-64"
                />
                <button type="submit" className="bg-[#10b981] hover:bg-[#0d9668] text-white p-2.5 rounded-xl font-bold">
                  <Search className="w-4 h-4" />
                </button>
                <button type="button" onClick={resetSearch} className="text-xs font-semibold text-slate-500 hover:text-slate-800 px-2">
                  Clear
                </button>
              </form>
            </div>

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              
              {/* Best Overall Deal */}
              <div className="col-span-2 bg-gradient-to-br from-[#e6f7f0] to-[#f4fbf8] border border-[#10b981]/20 p-5 rounded-2xl flex items-center gap-4 relative overflow-hidden">
                <div className="bg-white p-2.5 rounded-xl shadow-xs border border-emerald-50">
                  <TrendingUp className="w-8 h-8 text-[#10b981]" />
                </div>
                <div className="z-10">
                  <p className="text-[10px] font-black text-emerald-800 uppercase tracking-wider">Best Match Deal</p>
                  <p className="font-bold text-[#0f172a] text-sm line-clamp-1">{results.best_deal?.name || 'N/A'}</p>
                  <p className="text-xl font-black text-[#10b981] mt-0.5">
                    ₹{results.best_deal?.price} 
                    {results.savings > 0 && <span className="text-xs font-bold text-slate-400 line-through ml-2">₹{results.best_deal?.mrp}</span>}
                  </p>
                </div>
                <div className="absolute right-4 top-4">
                  <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border ${getStoreBadgeColor(results.best_deal?.source || '')}`}>
                    {results.best_deal?.source}
                  </span>
                </div>
              </div>

              {/* Total Savings */}
              <div className="bg-white border border-slate-100 p-5 rounded-2xl flex items-center gap-4 shadow-xs">
                <div className="bg-emerald-50 p-2.5 rounded-xl text-emerald-600">
                  <Percent className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-wider">Maximum Savings</p>
                  <p className="text-2xl font-black text-[#0f172a]">₹{results.savings || 0}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">vs MRP tags</p>
                </div>
              </div>

              {/* Platforms Checked */}
              <div className="bg-white border border-slate-100 p-5 rounded-2xl flex items-center gap-4 shadow-xs">
                <div className="bg-blue-50 p-2.5 rounded-xl text-blue-600">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-wider">Stores Scanned</p>
                  <p className="text-2xl font-black text-[#0f172a]">
                    {Object.keys(results.source_stats || {}).length}
                  </p>
                  <p className="text-[10px] text-slate-400 mt-0.5">platforms local stock</p>
                </div>
              </div>

            </div>

            {/* AI Advisor Panel */}
            <div className="bg-gradient-to-tr from-slate-900 to-slate-800 text-white rounded-3xl p-6 md:p-8 shadow-md relative overflow-hidden border border-slate-700/30">
              {/* Background accent */}
              <div className="absolute top-0 right-0 w-64 h-64 bg-[#10b981]/10 rounded-full blur-3xl pointer-events-none"></div>
              
              <div className="flex items-center gap-2 mb-4">
                <div className="bg-[#10b981]/20 p-2 rounded-xl text-[#10b981]">
                  <Sparkles className="w-5 h-5" />
                </div>
                <h3 className="font-display font-extrabold text-lg tracking-tight">AI Grocery Advisor</h3>
                {aiLoading && <Loader2 className="w-4 h-4 text-emerald-400 animate-spin ml-2" />}
              </div>

              {aiLoading ? (
                <div className="space-y-3 animate-pulse">
                  <div className="h-4 bg-slate-700 rounded-sm w-3/4"></div>
                  <div className="h-4 bg-slate-700 rounded-sm w-5/6"></div>
                  <div className="h-4 bg-slate-700 rounded-sm w-2/3"></div>
                </div>
              ) : aiAnalysis ? (
                <div 
                  className="prose prose-invert max-w-none text-sm text-slate-300 leading-relaxed font-medium
                    [&>h3]:text-white [&>h3]:font-bold [&>h3]:text-base [&>h3]:mt-4 [&>h3]:mb-1.5 [&>h3]:flex [&>h3]:items-center [&>h3]:gap-1
                    [&>p]:mb-3 [&>ul]:list-disc [&>ul]:pl-5 [&>ul]:space-y-1 [&>ul]:mb-3
                    [&>p>strong]:text-white [&>ul>li>strong]:text-[#10b981] [&>p>span]:text-emerald-400"
                  dangerouslySetInnerHTML={{ __html: aiAnalysis }}
                />
              ) : (
                <p className="text-sm text-slate-400">Requesting AI price analysis for this search query...</p>
              )}
            </div>

            {/* Comparison Controls (Tabs, Sort, Filter) */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mt-4 border-b border-slate-100 pb-4">
              
              {/* Tabs */}
              <div className="flex bg-slate-100 p-1 rounded-xl w-fit">
                <button
                  onClick={() => setActiveTab('grouped')}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    activeTab === 'grouped' 
                      ? 'bg-white text-slate-900 shadow-xs' 
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  Compare Side-by-Side
                </button>
                <button
                  onClick={() => setActiveTab('all')}
                  className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                    activeTab === 'all' 
                      ? 'bg-white text-slate-900 shadow-xs' 
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  All Matches ({results.products?.length || 0})
                </button>
              </div>

              {/* Filtering / Sorting (Only visible on All Matches) */}
              <div className="flex flex-wrap items-center gap-4">
                
                {/* Store badges selector */}
                <div className="flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-400">Store:</span>
                  <div className="flex gap-1">
                    {['all', 'Blinkit', 'Zepto', 'BigBasket', 'Instamart'].map((store) => (
                      <button
                        key={store}
                        onClick={() => setSelectedStore(store)}
                        className={`text-[10px] font-bold px-2.5 py-1.5 rounded-lg border transition-all ${
                          selectedStore === store
                            ? 'bg-slate-800 text-white border-slate-800'
                            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        {store === 'all' ? 'All' : store}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Sort dropdown */}
                {activeTab === 'all' && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-slate-400">Sort By:</span>
                    <select
                      value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}
                      className="bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-700 px-2.5 py-1.5 outline-none focus:border-[#10b981]"
                    >
                      <option value="price">Price: Low to High</option>
                      <option value="unit_price">Unit Price (per kg/L)</option>
                      <option value="score">Relevance Rank</option>
                    </select>
                  </div>
                )}

              </div>
            </div>

            {/* TAB: COMPARISON SIDE-BY-SIDE */}
            {activeTab === 'grouped' && (
              <div className="flex flex-col gap-6">
                {results.grouped_products && results.grouped_products.length > 0 ? (
                  results.grouped_products.map((group, idx) => {
                    // Find the cheapest product in this group
                    const sortedGroupProducts = [...group.products].sort((a, b) => a.price - b.price)
                    const cheapestPrice = sortedGroupProducts[0]?.price

                    return (
                      <div key={idx} className="bg-white border border-slate-100 rounded-3xl p-5 md:p-6 shadow-xs flex flex-col md:flex-row gap-6 items-start md:items-center">
                        
                        {/* Group info */}
                        <div className="flex items-center gap-4 min-w-[250px] md:max-w-[320px] w-full">
                          <div className="w-20 h-20 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center p-2 shrink-0">
                            {group.image ? (
                              <img src={group.image} alt={group.name} className="max-w-full max-h-full object-contain" />
                            ) : (
                              <ShoppingBag className="w-8 h-8 text-slate-300" />
                            )}
                          </div>
                          <div>
                            <h3 className="font-bold text-slate-800 leading-snug line-clamp-2">{group.name}</h3>
                            <p className="text-xs text-slate-400 font-semibold mt-1">Pack Size: {group.quantity || 'Standard Pack'}</p>
                          </div>
                        </div>

                        {/* Store listings compare */}
                        <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
                          {['Blinkit', 'Zepto', 'Instamart', 'BigBasket'].map((platform) => {
                            const platformProduct = group.products.find(p => p.source.toLowerCase() === platform.toLowerCase())
                            const isCheapest = platformProduct && platformProduct.price === cheapestPrice

                            return (
                              <div 
                                key={platform}
                                className={`p-4 rounded-2xl border transition-all ${
                                  platformProduct 
                                    ? isCheapest
                                      ? 'bg-emerald-50/40 border-[#10b981] ring-1 ring-[#10b981]/10'
                                      : 'bg-slate-50/50 border-slate-100'
                                    : 'bg-slate-50/20 border-slate-100/50 opacity-40'
                                }`}
                              >
                                <div className="flex items-center justify-between mb-2">
                                  <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full border ${getStoreBadgeColor(platform)}`}>
                                    {platform}
                                  </span>
                                  {isCheapest && (
                                    <span className="bg-[#10b981] text-white text-[8px] font-extrabold px-1.5 py-0.5 rounded-md">Best</span>
                                  )}
                                </div>

                                {platformProduct ? (
                                  <div className="space-y-1">
                                    <div className="text-lg font-black text-slate-800">
                                      ₹{platformProduct.price}
                                      {platformProduct.mrp > platformProduct.price && (
                                        <span className="text-[10px] font-bold text-slate-400 line-through ml-1.5">
                                          ₹{platformProduct.mrp}
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-[10px] text-slate-400 truncate line-clamp-1">{platformProduct.name}</p>
                                    
                                    {platformProduct.link ? (
                                      <a 
                                        href={platformProduct.link} 
                                        target="_blank" 
                                        rel="noopener noreferrer" 
                                        className="text-[10px] font-bold text-[#10b981] hover:underline flex items-center gap-0.5 pt-1.5"
                                      >
                                        Buy on {platform} <ExternalLink className="w-2.5 h-2.5" />
                                      </a>
                                    ) : (
                                      <p className="text-[9px] text-slate-400 italic pt-1">In stock</p>
                                    )}
                                  </div>
                                ) : (
                                  <div className="py-2 text-[10px] font-medium text-slate-400 italic">Not found / Out of stock</div>
                                )}
                              </div>
                            )
                          })}
                        </div>

                      </div>
                    )
                  })
                ) : (
                  <div className="bg-white border border-slate-100 rounded-3xl p-12 text-center text-slate-400 font-medium">
                    No grouped products available. Try looking in "All Matches" or change your keywords.
                  </div>
                )}
              </div>
            )}

            {/* TAB: ALL MATCHES */}
            {activeTab === 'all' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                {getSortedProducts().map((product, idx) => (
                  <div key={idx} className="bg-white border border-slate-100 hover:border-slate-200 rounded-3xl p-4 shadow-xs flex flex-col justify-between hover:scale-[1.01] transition-all">
                    <div>
                      {/* Product image & store badge */}
                      <div className="relative aspect-square w-full rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center p-4 mb-4">
                        {product.image ? (
                          <img src={product.image} alt={product.name} className="max-h-full max-w-full object-contain" />
                        ) : (
                          <ShoppingBag className="w-12 h-12 text-slate-300" />
                        )}
                        <span className={`absolute top-2 left-2 text-[9px] font-black uppercase px-2 py-0.5 rounded-full border shadow-2xs ${getStoreBadgeColor(product.source)}`}>
                          {product.source}
                        </span>
                      </div>

                      {/* Product details */}
                      <div className="space-y-1">
                        <h4 className="font-bold text-slate-800 text-sm leading-snug line-clamp-2 min-h-[40px]">{product.name}</h4>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-bold text-slate-400 bg-slate-50 border border-slate-100 px-2 py-0.5 rounded-md">
                            {product.quantity || '1 unit'}
                          </span>
                          {product.unit_price && product.unit_price !== product.price && (
                            <span className="text-[9px] font-semibold text-slate-400">
                              (₹{(product.unit_price).toFixed(1)}/kg)
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Price and Action */}
                    <div className="mt-4 pt-4 border-t border-slate-50 flex items-center justify-between">
                      <div>
                        <div className="text-base font-black text-slate-800">₹{product.price}</div>
                        {product.mrp > product.price && (
                          <div className="text-[10px] font-bold text-slate-400 line-through">₹{product.mrp}</div>
                        )}
                      </div>

                      {product.link ? (
                        <a 
                          href={product.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="bg-slate-50 hover:bg-[#10b981] hover:text-white text-slate-700 p-2 rounded-xl transition-all border border-slate-100 hover:border-transparent flex items-center justify-center"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      ) : (
                        <span className="text-[10px] font-medium text-slate-400 bg-slate-50 px-2.5 py-1.5 rounded-lg border border-slate-100">Local Only</span>
                      )}
                    </div>
                  </div>
                ))}

                {getSortedProducts().length === 0 && (
                  <div className="col-span-full py-16 text-center text-slate-400 font-medium">
                    No products match the selected filters.
                  </div>
                )}
              </div>
            )}

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-100 py-8 px-6 mt-16">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-slate-400 text-xs font-semibold">
          <div className="flex items-center gap-2">
            <span className="font-display font-extrabold text-slate-600">ShopSmart<span className="text-[#10b981]">AI</span></span>
            <span>•</span>
            <span>© 2026. Scraped live for educational purposes only.</span>
          </div>
          <div className="flex gap-4">
            <span className="text-slate-300">Compare grocery prices instantly across major apps.</span>
          </div>
        </div>
      </footer>

    </div>
  )
}

export default App
