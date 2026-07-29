// Global Variables
let useCasesData = {};
let activeUseCaseId = "";
let viewingChunks = false;
let customDocumentText = "";  // Stores the contents of the uploaded text file

// DOM Elements
const useCasesList = document.getElementById("use-cases-list");
const useCaseTitle = document.getElementById("use-case-title");
const useCaseDesc = document.getElementById("use-case-desc");
const useCasePersona = document.getElementById("use-case-persona");
const documentDisplay = document.getElementById("document-display");
const uploadContainer = document.getElementById("upload-container");
const fileInput = document.getElementById("file-input");
const uploadDropzone = document.getElementById("upload-dropzone");
const uploadIdleState = document.getElementById("upload-idle-state");
const uploadSuccessState = document.getElementById("upload-success-state");
const uploadFileDetails = document.getElementById("upload-file-details");
const paramCustomPersona = document.getElementById("param-custom-persona");

const chunksDisplay = document.getElementById("chunks-display");
const chunksList = document.getElementById("chunks-list");
const chunkCountBadge = document.getElementById("chunk-count-badge");
const toggleChunksBtn = document.getElementById("toggle-chunks-btn");

const settingsToggleBtn = document.getElementById("settings-toggle-btn");
const settingsBody = document.getElementById("settings-body");
const settingsArrow = document.getElementById("settings-arrow");

const paramMaxWords = document.getElementById("param-max-words");
const paramOverlap = document.getElementById("param-overlap");
const paramTopK = document.getElementById("param-top-k");

const queryInput = document.getElementById("query-input");
const runRagBtn = document.getElementById("run-rag-btn");
const queryPillsList = document.getElementById("query-pills-list");

const resultsTabs = document.querySelectorAll(".results-tab");
const tabContentAnswer = document.getElementById("tab-content-answer");
const tabContentRetrieved = document.getElementById("tab-content-retrieved");

const answerEmpty = document.getElementById("answer-empty");
const answerLoading = document.getElementById("answer-loading");
const answerDisplayBox = document.getElementById("answer-display-box");
const answerText = document.getElementById("answer-text");

const retrievedEmpty = document.getElementById("retrieved-empty");
const retrievedChunksList = document.getElementById("retrieved-chunks-list");

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    fetchUseCases();
    setupEventListeners();
    setupFileUpload();
});

// Event Listeners
function setupEventListeners() {
    // Toggle Chunks vs Document View
    toggleChunksBtn.addEventListener("click", () => {
        viewingChunks = !viewingChunks;
        if (viewingChunks) {
            documentDisplay.classList.add("hidden");
            uploadContainer.classList.add("hidden");
            chunksDisplay.classList.remove("hidden");
            toggleChunksBtn.querySelector("span").textContent = "View Document";
            toggleChunksBtn.querySelector("i").setAttribute("data-lucide", "file-text");
            // Regenerate chunks list in case parameters were altered
            generateLocalChunks();
        } else {
            if (activeUseCaseId === "custom_upload") {
                uploadContainer.classList.remove("hidden");
            } else {
                documentDisplay.classList.remove("hidden");
            }
            chunksDisplay.classList.add("hidden");
            toggleChunksBtn.querySelector("span").textContent = "View Chunks";
            toggleChunksBtn.querySelector("i").setAttribute("data-lucide", "layers");
        }
        lucide.createIcons();
    });

    // Toggle Parameter Settings
    settingsToggleBtn.addEventListener("click", () => {
        settingsBody.classList.toggle("hidden");
        settingsArrow.classList.toggle("rotated");
    });

    // Run RAG Query
    runRagBtn.addEventListener("click", executeQuery);
    queryInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            executeQuery();
        }
    });

    // Results Tab Switching
    resultsTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            resultsTabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            
            const targetTab = tab.getAttribute("data-tab");
            if (targetTab === "answer") {
                tabContentAnswer.classList.add("active");
                tabContentRetrieved.classList.remove("active");
            } else {
                tabContentAnswer.classList.remove("active");
                tabContentRetrieved.classList.add("active");
            }
        });
    });
}

// Setup File Upload Interactions
function setupFileUpload() {
    // Handle File Browser Select
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleUploadedFile(e.target.files[0]);
        }
    });

    // Handle Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadDropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadDropzone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadDropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadDropzone.classList.remove('dragover');
        }, false);
    });

    uploadDropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleUploadedFile(files[0]);
        }
    });
}

// Process local text file
function handleUploadedFile(file) {
    if (!file.name.endsWith('.txt')) {
        alert("Only plain text (.txt) files are supported!");
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        customDocumentText = e.target.result;
        
        // Hide idle state, show success state
        const wordCount = customDocumentText.split(/\s+/).filter(w => w.length > 0).length;
        uploadIdleState.classList.add("hidden");
        uploadSuccessState.classList.remove("hidden");
        uploadFileDetails.textContent = `${file.name} (${wordCount} words, ${customDocumentText.length} characters)`;
        
        lucide.createIcons();

        // Update local chunks rendering
        generateLocalChunks();
    };
    reader.readAsText(file);
}

// Fetch Use Cases Config from Server
async function fetchUseCases() {
    try {
        const response = await fetch("/api/usecases");
        useCasesData = await response.json();
        renderSidebar();
        
        // Select the first use case by default
        const firstKey = Object.keys(useCasesData)[0];
        if (firstKey) {
            selectUseCase(firstKey);
        }
    } catch (error) {
        console.error("Error fetching use cases:", error);
    }
}

// Render Use Cases in the Sidebar including custom upload option
function renderSidebar() {
    useCasesList.innerHTML = "";
    
    // Render standard use cases
    Object.keys(useCasesData).forEach(key => {
        const useCase = useCasesData[key];
        const item = document.createElement("div");
        item.className = `nav-item ${key === activeUseCaseId ? 'active' : ''}`;
        item.id = `nav-${key}`;
        item.innerHTML = `
            <span class="nav-title">${useCase.title}</span>
            <span class="nav-desc">${useCase.description}</span>
        `;
        item.addEventListener("click", () => selectUseCase(key));
        useCasesList.appendChild(item);
    });

    // Add Custom Upload tab at the bottom
    const customItem = document.createElement("div");
    customItem.className = `nav-item ${activeUseCaseId === 'custom_upload' ? 'active' : ''}`;
    customItem.id = "nav-custom_upload";
    customItem.innerHTML = `
        <span class="nav-title" style="color: var(--primary)">📁 Custom Document Upload</span>
        <span class="nav-desc">Upload your own .txt file notes and query them.</span>
    `;
    customItem.addEventListener("click", () => selectUseCase("custom_upload"));
    useCasesList.appendChild(customItem);
}

// Select Active Use Case
function selectUseCase(key) {
    activeUseCaseId = key;
    
    // Update active class in sidebar
    document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
    document.getElementById(`nav-${key}`).classList.add("active");
    
    // Reset view to Document/Upload (not chunks list)
    viewingChunks = false;
    chunksDisplay.classList.add("hidden");
    toggleChunksBtn.querySelector("span").textContent = "View Chunks";
    toggleChunksBtn.querySelector("i").setAttribute("data-lucide", "layers");
    
    if (key === "custom_upload") {
        // Toggle viewports
        documentDisplay.classList.add("hidden");
        uploadContainer.classList.remove("hidden");

        useCaseTitle.textContent = "📁 Custom Document RAG";
        useCaseDesc.textContent = "Upload your own study notes, policy guides, or textual files (.txt) and query them.";
        useCasePersona.querySelector("span").textContent = "Persona: Custom AI Assistant";

        // Reset inputs to standard defaults
        paramMaxWords.value = 80;
        paramOverlap.value = 15;
        paramTopK.value = 2;

        renderQueryPills([]); // Clear predefined pills
        clearOutputs();
        generateLocalChunks(); // Display count for custom
    } else {
        documentDisplay.classList.remove("hidden");
        uploadContainer.classList.add("hidden");

        const useCase = useCasesData[key];
        
        // Update header info
        useCaseTitle.textContent = useCase.title;
        useCaseDesc.textContent = useCase.description;
        useCasePersona.querySelector("span").textContent = `Persona: ${useCase.persona}`;
        
        // Update Parameters Inputs
        paramMaxWords.value = useCase.default_max_words;
        paramOverlap.value = useCase.default_overlap;
        paramTopK.value = useCase.default_top_k;
        
        // Update Document Display
        documentDisplay.textContent = useCase.document;
        
        // Generate preloaded queries
        renderQueryPills(useCase.queries);
        clearOutputs();
        generateLocalChunks();
    }
    
    // Reinitialize Icons
    lucide.createIcons();
}

// Generate Preloaded Query Pills
function renderQueryPills(queries) {
    queryPillsList.innerHTML = "";
    queries.forEach(q => {
        const pill = document.createElement("div");
        pill.className = "query-pill";
        pill.textContent = q;
        pill.addEventListener("click", () => {
            queryInput.value = q;
            executeQuery();
        });
        queryPillsList.appendChild(pill);
    });
}

// Clear Outputs display
function clearOutputs() {
    answerText.innerHTML = "";
    answerDisplayBox.classList.add("hidden");
    answerEmpty.classList.remove("hidden");
    answerLoading.classList.add("hidden");
    
    retrievedEmpty.classList.remove("hidden");
    retrievedChunksList.innerHTML = "";
    
    // Switch to first tab (Answer)
    resultsTabs[0].click();
}

// Generate Chunks locally for the Sidebar/Document info panel
function generateLocalChunks() {
    let documentText = "";
    if (activeUseCaseId === "custom_upload") {
        documentText = customDocumentText;
    } else {
        documentText = useCasesData[activeUseCaseId].document;
    }

    if (!documentText) {
        chunkCountBadge.textContent = "0 Chunks";
        chunksList.innerHTML = `<div class="empty-state"><p>Please upload a text file to preview chunks.</p></div>`;
        return;
    }
    
    const maxWords = parseInt(paramMaxWords.value) || 80;
    const overlap = parseInt(paramOverlap.value) || 15;
    
    const words = documentText.split(/\s+/).filter(w => w.length > 0);
    const chunks = [];
    let i = 0;
    let chunkIdx = 0;
    
    while (i < words.length) {
        const chunkWords = words.slice(i, i + maxWords);
        const chunkText = chunkWords.join(" ");
        chunks.push({
            index: chunkIdx,
            text: chunkText
        });
        chunkIdx++;
        
        const step = Math.max(1, maxWords - overlap);
        i += step;
        if (i >= words.length) break;
    }
    
    // Update badge count
    chunkCountBadge.textContent = `${chunks.length} Chunks`;
    
    // Render in lists
    chunksList.innerHTML = "";
    chunks.forEach(chunk => {
        const card = document.createElement("div");
        card.className = "chunk-card";
        card.id = `chunk-card-${chunk.index}`;
        card.innerHTML = `
            <div class="chunk-card-header">
                <span>CHUNK ${chunk.index}</span>
            </div>
            <div class="chunk-card-body">${chunk.text}</div>
        `;
        chunksList.appendChild(card);
    });
}

// Execute RAG Query API Call
async function executeQuery() {
    const query = queryInput.value.trim();
    if (!query) return;
    
    const maxWords = parseInt(paramMaxWords.value) || 80;
    const overlap = parseInt(paramOverlap.value) || 15;
    const topK = parseInt(paramTopK.value) || 2;

    // Payload variables
    let payload = {
        usecase_id: activeUseCaseId,
        query: query,
        max_words: maxWords,
        overlap: overlap,
        top_k: topK
    };

    if (activeUseCaseId === "custom_upload") {
        if (!customDocumentText) {
            alert("Please upload a .txt notes file before running a query!");
            return;
        }
        payload.document = customDocumentText;
        payload.persona = paramCustomPersona.value.trim() || "a helpful assistant";
    }
    
    // Clear outputs, show loader
    answerEmpty.classList.add("hidden");
    answerLoading.classList.remove("hidden");
    answerDisplayBox.classList.add("hidden");
    
    retrievedEmpty.classList.add("hidden");
    retrievedChunksList.innerHTML = "";
    
    // Auto switch to Answer Tab
    resultsTabs[0].click();
    
    try {
        const response = await fetch("/api/query", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert("Error running query: " + data.error);
            clearOutputs();
            return;
        }
        
        // Hide loader, show result box
        answerLoading.classList.add("hidden");
        answerDisplayBox.classList.remove("hidden");
        
        // Format and render Answer Text with Interactive Citations
        answerText.innerHTML = formatAnswerCitations(data.answer);
        
        // Render Retrieved Chunks
        renderRetrievedChunks(data.retrieved_chunks);
        
        // Update chunks visual list details in case parameters changed on server
        renderAllChunksBadge(data.all_chunks);
        
    } catch (error) {
        console.error("Error executing query:", error);
        alert("Server communication error.");
        clearOutputs();
    }
}

// Format Citation strings like [Source X] into clickable links
function formatAnswerCitations(text) {
    // Regex matches [Source X] where X is an integer
    return text.replace(/\[Source\s+(\d+)\]/g, (match, index) => {
        return `<span class="citation-link" onclick="highlightChunkCard(${index})">[Source ${index}]</span>`;
    });
}

// Scroll to and highlight a specific chunk card when citation is clicked
function highlightChunkCard(index) {
    // Switch view to chunks panel if not already there
    if (!viewingChunks) {
        toggleChunksBtn.click();
    }
    
    // Find the chunk card
    const card = document.getElementById(`chunk-card-${index}`);
    if (card) {
        // Scroll into view
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        
        // Flash animation
        card.style.borderColor = "var(--primary)";
        card.style.boxShadow = "0 0 15px var(--primary-glow)";
        card.style.transform = "scale(1.02)";
        
        setTimeout(() => {
            card.style.borderColor = "var(--border-color)";
            card.style.boxShadow = "none";
            card.style.transform = "none";
        }, 2000);
    }
}

// Render Retrieved Chunks in the tab list
function renderRetrievedChunks(retrievedChunks) {
    retrievedChunksList.innerHTML = "";
    
    if (retrievedChunks.length === 0) {
        retrievedChunksList.innerHTML = `<div class="empty-state"><p>No chunks retrieved for this query.</p></div>`;
        return;
    }
    
    retrievedChunks.forEach(ret => {
        const pctScore = Math.round(ret.score * 100);
        
        const card = document.createElement("div");
        card.className = "retrieved-chunk-card";
        card.innerHTML = `
            <div class="retrieved-chunk-meta">
                <span>CHUNK ${ret.index}</span>
                <div class="score-visualizer">
                    <span class="text-xs">Cosine Similarity:</span>
                    <div class="score-bar-bg">
                        <div class="score-bar-fill" id="bar-${ret.index}"></div>
                    </div>
                    <span class="score-val">${ret.score.toFixed(4)}</span>
                </div>
            </div>
            <div class="retrieved-chunk-text">${ret.text}</div>
        `;
        
        retrievedChunksList.appendChild(card);
        
        // Trigger fill animation asynchronously
        setTimeout(() => {
            const fillBar = document.getElementById(`bar-${ret.index}`);
            if (fillBar) {
                fillBar.style.width = `${Math.max(0, pctScore)}%`;
            }
        }, 100);
    });
}

// Render All Chunks badge and updates standard listing if needed
function renderAllChunksBadge(allChunks) {
    chunkCountBadge.textContent = `${allChunks.length} Chunks`;
    
    // Re-fill local list in case parameters were altered on server
    chunksList.innerHTML = "";
    allChunks.forEach(chunk => {
        const card = document.createElement("div");
        card.className = "chunk-card";
        card.id = `chunk-card-${chunk.index}`;
        card.innerHTML = `
            <div class="chunk-card-header">
                <span>CHUNK ${chunk.index}</span>
            </div>
            <div class="chunk-card-body">${chunk.text}</div>
        `;
        chunksList.appendChild(card);
    });
}
