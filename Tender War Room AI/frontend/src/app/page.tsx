"use client";

import React, { useState, useEffect } from "react";

export default function Home() {
  // Auth state
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  const [usernameInput, setUsernameInput] = useState("admin");
  const [passwordInput, setPasswordInput] = useState("admin123");
  const [authError, setAuthError] = useState("");

  // Data state
  const [tenders, setTenders] = useState<any[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string | null>(null);
  const [selectedTender, setSelectedTender] = useState<any | null>(null);
  const [boqItems, setBoqItems] = useState<any[]>([]);
  const [recommendation, setRecommendation] = useState<any | null>(null);
  const [simulation, setSimulation] = useState<any | null>(null);

  // Scraper controls
  const [scrapingStatus, setScrapingStatus] = useState<string | null>(null);
  const [celeryTaskId, setCeleryTaskId] = useState<string | null>(null);

  // Simulation Sliders state
  const [materialMultiplier, setMaterialMultiplier] = useState(0);
  const [labourMultiplier, setLabourMultiplier] = useState(0);
  const [proposedBidDeviation, setProposedBidDeviation] = useState(-5.0);
  const [overheadPercent, setOverheadPercent] = useState(10.0);
  const [taxPercent, setTaxPercent] = useState(5.0);

  // Edit rates state
  const [editingRates, setEditingRates] = useState<{ [itemNumber: string]: string }>({});

  const API_URL = "http://localhost:8000/api/v1";

  // Check for stored token
  useEffect(() => {
    const savedToken = localStorage.getItem("token");
    if (savedToken) {
      setToken(savedToken);
      fetchUser(savedToken);
    }
  }, []);

  // Fetch tenders list when token is available
  useEffect(() => {
    if (token) {
      fetchTenders();
    }
  }, [token]);

  // Handle tender selection
  useEffect(() => {
    if (token && selectedTenderId) {
      fetchTenderDetail(selectedTenderId);
    }
  }, [selectedTenderId]);

  // Recalculate simulation dynamically when sliders move
  useEffect(() => {
    if (token && selectedTenderId) {
      const delayDebounce = setTimeout(() => {
        runSimulation();
      }, 300);
      return () => clearTimeout(delayDebounce);
    }
  }, [materialMultiplier, labourMultiplier, proposedBidDeviation, overheadPercent, taxPercent, selectedTenderId]);

  // Auth fetch user profile
  const fetchUser = async (authToken: string) => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer {authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUser({ username: data.username, role: data.role });
      } else {
        handleLogout();
      }
    } catch {
      handleLogout();
    }
  };

  // Sign In handler
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    try {
      const formData = new URLSearchParams();
      formData.append("username", usernameInput);
      formData.append("password", passwordInput);

      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("token", data.access_token);
        setToken(data.access_token);
        fetchUser(data.access_token);
      } else {
        const errData = await res.json();
        setAuthError(errData.detail || "Authentication failed. Try admin / admin123");
      }
    } catch {
      setAuthError("Failed to reach auth gateway.");
    }
  };

  // Log Out handler
  const handleLogout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    setTenders([]);
    setSelectedTenderId(null);
    setSelectedTender(null);
    setRecommendation(null);
    setSimulation(null);
  };

  // Fetch tenders list
  const fetchTenders = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/tenders/`, {
        headers: { Authorization: `Bearer {token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTenders(data);
      }
    } catch (err) {
      console.error("Failed to load tenders", err);
    }
  };

  // Fetch single tender and populate details
  const fetchTenderDetail = async (id: string) => {
    if (!token) return;
    try {
      // 1. Fetch metadata
      const resMeta = await fetch(`${API_URL}/tenders/${id}`, {
        headers: { Authorization: `Bearer {token}` },
      });
      if (resMeta.ok) {
        const meta = await resMeta.json();
        setSelectedTender(meta);
        setBoqItems(meta.boq_items || []);
        
        // Populate edit inputs
        const initialEditRates: any = {};
        (meta.boq_items || []).forEach((item: any) => {
          if (item.contractor_rate !== null) {
            initialEditRates[item.item_number] = String(item.contractor_rate);
          }
        });
        setEditingRates(initialEditRates);
      }

      // 2. Fetch AI strategy recommendation
      // Run POST first to initialize it
      await fetch(`${API_URL}/recommendations/${id}`, {
        method: "POST",
        headers: { Authorization: `Bearer {token}` },
      });
      const resRec = await fetch(`${API_URL}/recommendations/${id}`, {
        headers: { Authorization: `Bearer {token}` },
      });
      if (resRec.ok) {
        const recData = await resRec.json();
        setRecommendation(recData);
        // Default proposed bid deviation slider to recommended range min
        if (recData.recommended_bid_range) {
          setProposedBidDeviation(recData.recommended_bid_range.min_percent);
        }
      }
    } catch (err) {
      console.error("Failed to retrieve tender specs", err);
    }
  };

  // Update customized BOQ items
  const handleUpdateRates = async () => {
    if (!token || !selectedTenderId) return;
    const ratesList = Object.keys(editingRates).map((itemNum) => ({
      item_number: itemNum,
      contractor_rate: parseFloat(editingRates[itemNum]) || 0.0,
    }));

    try {
      const res = await fetch(`${API_URL}/estimates/${selectedTenderId}/boq-rates`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer {token}`,
        },
        body: JSON.stringify(ratesList),
      });

      if (res.ok) {
        // Refresh tender details
        fetchTenderDetail(selectedTenderId);
        alert("BOQ Rates updated and persisted successfully!");
      }
    } catch (err) {
      alert("Failed to save rate sheets.");
    }
  };

  // Run What-If Simulation sensitivity run
  const runSimulation = async () => {
    if (!token || !selectedTenderId) return;
    try {
      const res = await fetch(
        `${API_URL}/simulations/${selectedTenderId}/run` +
          `?material_multiplier=${materialMultiplier}` +
          `&labour_multiplier=${labourMultiplier}` +
          `&proposed_bid_deviation=${proposedBidDeviation}` +
          `&overhead_percent=${overheadPercent}` +
          `&tax_percent=${taxPercent}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer {token}` },
        }
      );
      if (res.ok) {
        const simData = await res.json();
        setSimulation(simData);
      }
    } catch (err) {
      console.error("Simulation run failed", err);
    }
  };

  // Trigger scraper jobs
  const handleTriggerScraper = async (portal: string) => {
    if (!token) return;
    setScrapingStatus("Queueing scraper task...");
    try {
      const res = await fetch(`${API_URL}/tenders/scrape?portal_name=${portal}`, {
        method: "POST",
        headers: { Authorization: `Bearer {token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setCeleryTaskId(data.task_id);
        setScrapingStatus(`Scraper running in background (Task: ${data.task_id.substring(0, 8)}...)`);
        pollScraperTask(data.task_id);
      }
    } catch {
      setScrapingStatus("Scraper job failed to start.");
    }
  };

  // Poll background Celery scraper
  const pollScraperTask = async (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/tenders/tasks/${taskId}`, {
          headers: { Authorization: `Bearer {token}` },
        });
        if (res.ok) {
          const statusData = await res.json();
          if (statusData.status === "SUCCESS") {
            setScrapingStatus("Scraping completed! Refreshing list...");
            setCeleryTaskId(null);
            fetchTenders();
            clearInterval(interval);
            setTimeout(() => setScrapingStatus(null), 5000);
          } else if (statusData.status === "FAILURE") {
            setScrapingStatus("Scraping worker reported a failure.");
            setCeleryTaskId(null);
            clearInterval(interval);
          } else {
            setScrapingStatus(`Scraper running: ${statusData.status}...`);
          }
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
  };

  // Login Screen render
  if (!token || !user) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-600 to-indigo-600"></div>
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold tracking-tight text-blue-500 mb-1">TENDER WAR ROOM AI</h1>
            <p className="text-xs text-slate-400 uppercase tracking-widest font-semibold">Decision Support Portal</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Username</label>
              <input
                type="text"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                value={usernameInput}
                onChange={(e) => setUsernameInput(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Password</label>
              <input
                type="password"
                className="w-full bg-slate-955 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
              />
            </div>

            {authError && <div className="text-xs text-red-500 text-center font-semibold bg-red-955/30 border border-red-900/50 py-2 rounded-lg">{authError}</div>}

            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold text-sm py-3 rounded-lg transition-colors cursor-pointer"
            >
              Sign In to Command Center
            </button>
          </form>

          <div className="text-center mt-6 text-slate-500 text-xs">
            Admin Defaults: <code className="bg-slate-950 px-1.5 py-0.5 rounded border border-slate-850">admin / admin123</code>
          </div>
        </div>
      </main>
    );
  }

  // Dashboard render
  return (
    <main className="min-h-screen bg-slate-955 text-slate-100 font-sans flex flex-col">
      {/* Top Bar Navigation */}
      <header className="h-16 border-b border-slate-900 bg-slate-900/40 backdrop-blur-md px-6 flex justify-between items-center shrink-0">
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span className="text-lg font-bold tracking-tight text-blue-500">TENDER WAR ROOM AI</span>
          <span className="bg-blue-500/10 text-blue-400 text-[10px] px-2 py-0.5 rounded-full font-semibold border border-blue-500/20 uppercase tracking-wider">
            {user.role} Portal
          </span>
        </div>

        {/* Global Controls & Status */}
        <div className="flex items-center gap-6">
          {scrapingStatus && (
            <span className="text-xs font-semibold bg-blue-955/50 border border-blue-900 text-blue-400 px-3 py-1.5 rounded-lg animate-pulse">
              {scrapingStatus}
            </span>
          )}
          
          <div className="flex gap-2">
            <button
              onClick={() => handleTriggerScraper("SCCL")}
              disabled={!!celeryTaskId}
              className="bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-semibold px-3.5 py-2 rounded-lg border border-slate-800 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Trigger SCCL Scrape
            </button>
            <button
              onClick={() => handleTriggerScraper("Telangana eProcurement")}
              disabled={!!celeryTaskId}
              className="bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-semibold px-3.5 py-2 rounded-lg border border-slate-800 transition-colors disabled:opacity-50 cursor-pointer"
            >
              Trigger Telangana Scrape
            </button>
          </div>

          <div className="flex items-center gap-3 pl-4 border-l border-slate-900">
            <span className="text-sm font-semibold text-slate-300">{user.username}</span>
            <button
              onClick={handleLogout}
              className="text-slate-400 hover:text-red-500 transition-colors text-xs font-semibold cursor-pointer"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Grid Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - Scraped Tenders List */}
        <aside className="w-80 border-r border-slate-900 bg-slate-900/10 flex flex-col shrink-0">
          <div className="p-4 border-b border-slate-900 shrink-0">
            <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400">Scraped Tenders Folder</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {tenders.length === 0 ? (
              <div className="text-slate-500 text-xs text-center mt-8">No tenders scraped yet. Try triggering a scraper!</div>
            ) : (
              tenders.map((tender) => (
                <button
                  key={tender.id}
                  onClick={() => setSelectedTenderId(tender.id)}
                  className={`w-full text-left p-3.5 rounded-lg border transition-all cursor-pointer block ${
                    selectedTenderId === tender.id
                      ? "bg-blue-600/10 border-blue-500 text-slate-100 shadow-lg"
                      : "bg-slate-900/40 border-slate-900 hover:bg-slate-900/80 hover:border-slate-800 text-slate-400"
                  }`}
                >
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                    {tender.tender_number}
                  </div>
                  <div className="text-xs font-semibold line-clamp-2 leading-relaxed mb-2 text-slate-300">
                    {tender.work_name}
                  </div>
                  <div className="flex justify-between items-center text-[10px] font-semibold">
                    <span className="text-emerald-500">
                      Rs. {tender.estimated_cost ? tender.estimated_cost.toLocaleString() : "-"}
                    </span>
                    <span className="text-slate-550">{tender.status}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        {/* Right Detail Strategy Panel */}
        <section className="flex-1 overflow-y-auto p-6 bg-slate-955">
          {!selectedTender ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <div className="h-16 w-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mb-4 text-blue-500 text-xl font-bold">
                🎯
              </div>
              <h2 className="text-lg font-bold text-slate-300 mb-1">Bidding Strategic Workspace</h2>
              <p className="text-sm text-slate-550 max-w-sm">Select a government tender from the left sidebar to start custom cost overrides and AI win probability simulations.</p>
            </div>
          ) : (
            <div className="space-y-6 max-w-5xl mx-auto">
              
              {/* Tender Specs Top Header */}
              <div className="bg-slate-900/30 border border-slate-900 rounded-xl p-6 relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-600 to-indigo-600"></div>
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-400 px-2 py-0.5 rounded border border-slate-700">
                      {selectedTender.tender_number}
                    </span>
                    <h2 className="text-lg font-bold text-slate-100 mt-2 leading-relaxed">{selectedTender.work_name}</h2>
                  </div>
                  <a
                    href={`http://localhost:8000/api/v1/reports/${selectedTenderId}/print`}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs px-4 py-2.5 rounded-lg transition-colors flex items-center gap-2 cursor-pointer shadow-lg shadow-blue-600/10"
                  >
                    📄 Export Printable Dossier
                  </a>
                </div>

                <div className="grid grid-cols-3 gap-6 pt-4 border-t border-slate-900 text-xs">
                  <div>
                    <span className="block text-slate-500 font-semibold mb-1 uppercase tracking-wider text-[10px]">Portal Source</span>
                    <span className="text-slate-300 font-semibold">{selectedTender.portal_name || "Telangana eProcurement"}</span>
                  </div>
                  <div>
                    <span className="block text-slate-500 font-semibold mb-1 uppercase tracking-wider text-[10px]">Closing Date</span>
                    <span className="text-slate-300 font-semibold">
                      {selectedTender.closing_date ? new Date(selectedTender.closing_date).toLocaleDateString() : "Pending Extraction"}
                    </span>
                  </div>
                  <div>
                    <span className="block text-slate-500 font-semibold mb-1 uppercase tracking-wider text-[10px]">Tender EMD</span>
                    <span className="text-emerald-500 font-bold">
                      Rs. {selectedTender.emd ? selectedTender.emd.toLocaleString() : "TBD"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Cost Simulation / Win Probability Grid */}
              <div className="grid grid-cols-3 gap-6">
                
                {/* Sliders Control Panel */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-xl p-5 space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-900 pb-2">Simulation parameters</h3>
                  
                  {/* Material Price Slider */}
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Material Inflation</span>
                      <span className={`font-semibold ${materialMultiplier >= 0 ? "text-red-500" : "text-emerald-500"}`}>
                        {materialMultiplier >= 0 ? "+" : ""}{materialMultiplier}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="-30"
                      max="30"
                      className="w-full h-1 bg-slate-950 rounded-lg appearance-none cursor-pointer"
                      value={materialMultiplier}
                      onChange={(e) => setMaterialMultiplier(parseInt(e.target.value))}
                    />
                  </div>

                  {/* Labour Slider */}
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Labour Shift</span>
                      <span className={`font-semibold ${labourMultiplier >= 0 ? "text-red-500" : "text-emerald-500"}`}>
                        {labourMultiplier >= 0 ? "+" : ""}{labourMultiplier}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="-30"
                      max="30"
                      className="w-full h-1 bg-slate-950 rounded-lg appearance-none cursor-pointer"
                      value={labourMultiplier}
                      onChange={(e) => setLabourMultiplier(parseInt(e.target.value))}
                    />
                  </div>

                  {/* Proposed Bid Deviation Slider */}
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Proposed Bidding Price</span>
                      <span className="font-semibold text-blue-400">{proposedBidDeviation > 0 ? "+" : ""}{proposedBidDeviation}%</span>
                    </div>
                    <input
                      type="range"
                      min="-20"
                      max="10"
                      step="0.1"
                      className="w-full h-1 bg-slate-950 rounded-lg appearance-none cursor-pointer"
                      value={proposedBidDeviation}
                      onChange={(e) => setProposedBidDeviation(parseFloat(e.target.value))}
                    />
                  </div>

                  {/* Overheads Markup */}
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Overhead Markup</span>
                      <span className="font-semibold text-slate-350">{overheadPercent}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="30"
                      step="0.5"
                      className="w-full h-1 bg-slate-950 rounded-lg appearance-none cursor-pointer"
                      value={overheadPercent}
                      onChange={(e) => setOverheadPercent(parseFloat(e.target.value))}
                    />
                  </div>

                  {/* Taxes Slider */}
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Compounding Taxes</span>
                      <span className="font-semibold text-slate-350">{taxPercent}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="20"
                      step="0.5"
                      className="w-full h-1 bg-slate-950 rounded-lg appearance-none cursor-pointer"
                      value={taxPercent}
                      onChange={(e) => setTaxPercent(parseFloat(e.target.value))}
                    />
                  </div>
                </div>

                {/* Simulated Cost Summary Sheet */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-xl p-5 space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-900 pb-2">Simulated Cost Sheet</h3>
                  
                  {simulation ? (
                    <div className="space-y-3.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Official Cost</span>
                        <span className="font-semibold">Rs. {simulation.official_estimated_cost.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Baseline Break-Even</span>
                        <span className="font-semibold">Rs. {simulation.original_break_even.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-900 pb-2">
                        <span className="text-slate-400">Simulated Break-Even</span>
                        <span className="font-bold text-slate-200">Rs. {simulation.simulated_break_even.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Proposed Proposal Bid</span>
                        <span className="font-bold text-blue-400">Rs. {simulation.proposed_bid.amount.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-900 pb-2">
                        <span className="text-slate-500">Expected Profit</span>
                        <span className={`font-bold ${simulation.proposed_bid.simulated_profit >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                          Rs. {simulation.proposed_bid.simulated_profit.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex justify-between items-center pt-2">
                        <span className="text-slate-400 font-semibold">Viability Status</span>
                        <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase ${
                          simulation.viability_status === "Viable" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
                        }`}>
                          {simulation.viability_status}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-xs text-center py-8">Simulating costs...</div>
                  )}
                </div>

                {/* AI Bidding Strategy Recommendation Gauge */}
                <div className="bg-slate-900/30 border border-slate-900 rounded-xl p-5 space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 border-b border-slate-900 pb-2">AI Strategy Metrics</h3>
                  
                  {simulation && recommendation ? (
                    <div className="space-y-4 text-xs text-center">
                      <div>
                        <div className="text-slate-500 font-semibold mb-1 uppercase tracking-wider text-[10px]">Win Probability</div>
                        <div className="text-3xl font-extrabold tracking-tight text-blue-500">
                          {simulation.proposed_bid.win_probability_percent.toFixed(1)}%
                        </div>
                      </div>
                      <div className="border-t border-slate-900 pt-3">
                        <div className="text-slate-500 font-semibold mb-1 uppercase tracking-wider text-[10px]">Recommended Optimal Bid Range</div>
                        <div className="text-sm font-bold text-emerald-400">
                          {recommendation.recommended_bid_range.min_percent.toFixed(2)}% to {recommendation.recommended_bid_range.max_percent.toFixed(2)}%
                        </div>
                      </div>
                      <div className="border-t border-slate-900 pt-3 text-left">
                        <div className="text-slate-500 font-semibold mb-1 uppercase tracking-wider text-[10px] text-center">AI Risk Rating</div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Complexity Score:</span>
                          <span className="font-bold text-amber-500">{recommendation.risk_score}/10</span>
                        </div>
                        <div className="flex justify-between items-center mt-1">
                          <span className="text-slate-400">Win Confidence:</span>
                          <span className="font-bold text-blue-400">{recommendation.confidence_level}</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-xs text-center py-8">Running AI Optimizer...</div>
                  )}
                </div>
              </div>

              {/* BOQ Customs Rate Editor */}
              <div className="bg-slate-900/30 border border-slate-900 rounded-xl p-5">
                <div className="flex justify-between items-center border-b border-slate-900 pb-2.5 mb-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Detailed Bill of Quantities (BOQ)</h3>
                  <button
                    onClick={handleUpdateRates}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-[11px] px-3.5 py-1.5 rounded-md transition-colors cursor-pointer"
                  >
                    Save Custom BOQ Rates
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-900 text-slate-400 font-semibold">
                        <th className="py-2.5 px-3">Item No</th>
                        <th className="py-2.5 px-3">Scope Description</th>
                        <th className="py-2.5 px-3">Quantity</th>
                        <th className="py-2.5 px-3">Unit</th>
                        <th className="py-2.5 px-3">Est. Rate</th>
                        <th className="py-2.5 px-3">Est. Amount</th>
                        <th className="py-2.5 px-3 text-blue-400">Contractor Custom Rate</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/40">
                      {boqItems.map((item) => (
                        <tr key={item.id} className="hover:bg-slate-900/10">
                          <td className="py-3 px-3 font-semibold text-slate-400">{item.item_number}</td>
                          <td className="py-3 px-3 font-medium text-slate-350 max-w-xs truncate">{item.description}</td>
                          <td className="py-3 px-3">{item.quantity}</td>
                          <td className="py-3 px-3 text-slate-500">{item.unit}</td>
                          <td className="py-3 px-3">Rs. {item.estimated_rate}</td>
                          <td className="py-3 px-3 font-semibold">Rs. {item.estimated_amount.toLocaleString()}</td>
                          <td className="py-2 px-2">
                            <input
                              type="number"
                              className="w-28 bg-slate-950 border border-slate-900 rounded px-2 py-1 text-xs text-slate-100 font-semibold focus:outline-none focus:border-blue-500"
                              value={editingRates[item.item_number] || ""}
                              placeholder="Rs. ..."
                              onChange={(e) =>
                                setEditingRates({
                                  ...editingRates,
                                  [item.item_number]: e.target.value,
                                })
                              }
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Gemini Risk Assumptions dossier Card */}
              {recommendation && (
                <div className="bg-red-500/5 border border-red-500/10 rounded-xl p-5 space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-red-400">Gemini Volatility & Assumptions Log</h3>
                  <div className="text-xs text-red-200/80 leading-relaxed">
                    <strong>Bidding Assumptions:</strong>
                    <ul className="list-disc list-inside mt-2 space-y-1">
                      {Object.keys(recommendation.assumptions || {}).map((key) => (
                        <li key={key}>
                          <span className="font-semibold text-slate-300">{key.replace(/_/g, " ").toUpperCase()}:</span>{" "}
                          {recommendation.assumptions[key]}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

            </div>
          )}
        </section>
      </div>
    </main>
  );
}
