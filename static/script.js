document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const usecaseSelect = document.getElementById('usecase-select');
    const maxWordsInput = document.getElementById('max-words');
    const maxWordsVal = document.getElementById('max-words-val');
    const overlapInput = document.getElementById('overlap');
    const overlapVal = document.getElementById('overlap-val');
    const topKInput = document.getElementById('top-k');
    const topKVal = document.getElementById('top-k-val');
    
    const customDocPanel = document.getElementById('custom-doc-panel');
    const customPersona = document.getElementById('custom-persona');
    const customText = document.getElementById('custom-text');
    const uploadZone = document.getElementById('upload-zone');
    const fileUploadInput = document.getElementById('file-upload-input');
    const uploadStatus = document.getElementById('upload-status');
    
    const usecaseTitle = document.getElementById('usecase-title');
    const usecaseDesc = document.getElementById('usecase-desc');
    const queriesContainer = document.getElementById('queries-container');
    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    
    const chatHistory = document.getElementById('chat-history');
    
    const retrievedList = document.getElementById('retrieved-list');
    const retrievedCount = document.getElementById('retrieved-count');
    const totalChunksCount = document.getElementById('total-chunks-count');
    const chunksGrid = document.getElementById('chunks-grid');
    
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    let usecasesData = {};
    let activeChunks = [];

    // Initialize highlight.js config
    hljs.configure({ ignoreUnescapedHTML: true });

    // Slider Listeners to update display label values dynamically
    maxWordsInput.addEventListener('input', (e) => {
        maxWordsVal.textContent = e.target.value;
    });
    overlapInput.addEventListener('input', (e) => {
        overlapVal.textContent = e.target.value;
    });
    topKInput.addEventListener('input', (e) => {
        topKVal.textContent = e.target.value;
    });

    // Tab switcher logic
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');
        });
    });

    // Fetch and populate use cases from the API
    async function fetchUsecases() {
        try {
            const res = await fetch('/api/usecases');
            if (!res.ok) throw new Error('Failed to retrieve use cases list');
            usecasesData = await res.json();
            
            // Clear and populate selector dropdown
            usecaseSelect.innerHTML = '';
            
            Object.keys(usecasesData).forEach(key => {
                const option = document.createElement('option');
                option.value = key;
                option.textContent = usecasesData[key].title;
                usecaseSelect.appendChild(option);
            });

            // Append a Custom RAG option for custom uploads
            const customOption = document.createElement('option');
            customOption.value = 'custom_upload';
            customOption.textContent = '➕ Create Custom RAG Context';
            usecaseSelect.appendChild(customOption);

            // Trigger initial loading update
            handleUsecaseChange(usecaseSelect.value);
            
        } catch (err) {
            console.error(err);
            usecaseTitle.textContent = 'Connection Error';
            usecaseDesc.textContent = 'Could not load configurations from server. Make sure app.py is running.';
        }
    }

    // Handles updates when switching configs
    function handleUsecaseChange(usecaseId) {
        // Clear custom text and upload status when switching use cases
        customText.value = '';
        uploadStatus.classList.add('hidden');
        uploadStatus.innerHTML = '';
        
        const personaInputContainer = document.getElementById('persona-input-container');

        if (usecaseId === 'custom_upload') {
            // Show Custom persona edit field
            if (personaInputContainer) personaInputContainer.classList.remove('hidden');
            usecaseTitle.textContent = 'Custom Grounded Knowledge Base';
            usecaseDesc.textContent = 'Upload custom documentation and configure custom system prompt instruction rules.';
            
            // Set input defaults
            maxWordsInput.value = 80;
            maxWordsVal.textContent = 80;
            overlapInput.value = 15;
            overlapVal.textContent = 15;
            topKInput.value = 2;
            topKVal.textContent = 2;
            
            customText.placeholder = 'Paste custom policy, log file, or document text here...';
            queriesContainer.innerHTML = '<span class="text-muted" style="font-size: 12px;">No queries predefined. Fill documentation details below and type your query directly.</span>';
        } else {
            // Preset configuration
            if (personaInputContainer) personaInputContainer.classList.add('hidden');
            const data = usecasesData[usecaseId];
            if (!data) return;
            
            usecaseTitle.textContent = data.title;
            usecaseDesc.textContent = data.description;
            
            // Set slider values to default values matching specifications
            maxWordsInput.value = data.default_max_words;
            maxWordsVal.textContent = data.default_max_words;
            overlapInput.value = data.default_overlap;
            overlapVal.textContent = data.default_overlap;
            topKInput.value = data.default_top_k;
            topKVal.textContent = data.default_top_k;

            customText.placeholder = 'Or override by uploading/pasting custom document text here...';

            // Render clickable predefined query chips
            queriesContainer.innerHTML = '';
            data.queries.forEach(query => {
                const chip = document.createElement('button');
                chip.className = 'suggest-btn';
                chip.textContent = query;
                chip.addEventListener('click', () => {
                    queryInput.value = query;
                    submitQuery();
                });
                queriesContainer.appendChild(chip);
            });
        }

        // Reset chat history feed, diagnostic lists, and mapping grid
        chatHistory.innerHTML = `
            <div class="chat-placeholder">
                <i class="fa-regular fa-comments chat-placeholder-icon"></i>
                <h3>RAG Chat Assistant</h3>
                <p>Ask a question about the active document. Uncheck <strong>Strict RAG Grounding</strong> in the sidebar to query Gemini's general knowledge.</p>
            </div>
        `;
        retrievedList.innerHTML = `
            <div class="empty-state">
                <i class="fa-regular fa-folder-open"></i>
                <p>Submit a query to inspect matched text chunks and cosine similarity scores.</p>
            </div>
        `;
        retrievedCount.textContent = '0';
        totalChunksCount.textContent = '0';
        chunksGrid.innerHTML = '';
    }

    usecaseSelect.addEventListener('change', (e) => {
        handleUsecaseChange(e.target.value);
    });

    // Execute query submission
    async function submitQuery() {
        const queryText = queryInput.value.trim();
        if (!queryText) return;

        const usecaseId = usecaseSelect.value;
        
        // Remove placeholder if present
        const placeholder = chatHistory.querySelector('.chat-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        // 1. Append User Bubble
        const userBubble = document.createElement('div');
        userBubble.className = 'chat-message user';
        userBubble.innerHTML = `<div class="message-content"></div>`;
        userBubble.querySelector('.message-content').textContent = queryText;
        chatHistory.appendChild(userBubble);
        
        // 2. Append Typing Bubble
        const botTyping = document.createElement('div');
        botTyping.className = 'chat-message bot typing';
        botTyping.id = 'bot-typing-indicator';
        botTyping.innerHTML = `
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        chatHistory.appendChild(botTyping);
        
        // Scroll to bottom
        chatHistory.scrollTop = chatHistory.scrollHeight;

        // Disable input during request
        submitBtn.disabled = true;
        queryInput.disabled = true;

        // Form post payload body
        const strictGroundingEl = document.getElementById('strict-grounding');
        const payload = {
            usecase_id: usecaseId,
            query: queryText,
            max_words: parseInt(maxWordsInput.value),
            overlap: parseInt(overlapInput.value),
            top_k: parseInt(topKInput.value),
            strict_grounding: strictGroundingEl ? strictGroundingEl.checked : true
        };

        const docText = customText.value.trim();
        if (docText) {
            payload.document = docText;
        }

        if (usecaseId === 'custom_upload') {
            payload.persona = customPersona.value.trim();
            
            if (payload.strict_grounding && !payload.document) {
                alert('Please input details into the Knowledge Source Text before submitting.');
                
                // Cleanup typing and return
                botTyping.remove();
                resetFormState();
                return;
            }
        }

        try {
            const res = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            // Remove typing bubble
            botTyping.remove();

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Server error processing RAG query');
            }

            const data = await res.json();
            
            // 3. Append Bot Bubble
            const botBubble = document.createElement('div');
            botBubble.className = 'chat-message bot';
            
            const badgeHtml = data.strict_grounding ? 
                `<span class="message-badge"><i class="fa-solid fa-circle-check"></i> Grounded Generation</span>` : 
                `<span class="message-badge info"><i class="fa-solid fa-brain"></i> General Generation</span>`;
            
            botBubble.innerHTML = `
                <div class="card-header-simple">
                    ${badgeHtml}
                    <button class="copy-msg-btn" title="Copy Answer"><i class="fa-regular fa-copy"></i></button>
                </div>
                <div class="message-content markdown-body"></div>
            `;
            
            // Parse Markdown safely
            botBubble.querySelector('.message-content').innerHTML = marked.parse(data.answer);
            
            // Highlight code blocks inside message bubble
            botBubble.querySelectorAll('pre code').forEach((el) => {
                hljs.highlightElement(el);
            });
            
            // Bind copy button listener dynamically to the bubble
            const msgCopyBtn = botBubble.querySelector('.copy-msg-btn');
            const msgContentEl = botBubble.querySelector('.message-content');
            msgCopyBtn.addEventListener('click', () => {
                const text = msgContentEl.innerText;
                navigator.clipboard.writeText(text).then(() => {
                    const origIcon = msgCopyBtn.innerHTML;
                    msgCopyBtn.innerHTML = '<i class="fa-solid fa-check" style="color: var(--success);"></i>';
                    setTimeout(() => {
                        msgCopyBtn.innerHTML = origIcon;
                    }, 1800);
                }).catch(err => {
                    console.error('Clipboard copy failed:', err);
                });
            });
            
            chatHistory.appendChild(botBubble);
            
            // 4. Render Retrieved Chunks (latest query)
            retrievedList.innerHTML = '';
            retrievedCount.textContent = data.retrieved_chunks.length;
            
            if (data.retrieved_chunks.length === 0) {
                retrievedList.innerHTML = `
                    <div class="empty-state">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <p>No document chunks were retrieved. Check if document content is empty.</p>
                    </div>
                `;
            } else {
                data.retrieved_chunks.forEach(item => {
                    const card = document.createElement('div');
                    card.className = 'chunk-card';
                    
                    let scoreClass = 'low';
                    if (item.score >= 0.35) {
                        scoreClass = 'high';
                    } else if (item.score >= 0.15) {
                        scoreClass = 'mid';
                    }

                    card.innerHTML = `
                        <div class="chunk-header">
                            <span class="chunk-source"><i class="fa-solid fa-cube"></i> Chunk [Source ${item.index}]</span>
                            <span class="similarity-badge ${scoreClass}">Similarity: ${item.score.toFixed(4)}</span>
                        </div>
                        <div class="chunk-text">${item.text}</div>
                    `;
                    retrievedList.appendChild(card);
                });
            }

            // 5. Render Document Index Grid
            totalChunksCount.textContent = data.all_chunks.length;
            chunksGrid.innerHTML = '';
            
            const retrievedIndices = new Set(data.retrieved_chunks.map(ch => ch.index));

            data.all_chunks.forEach(chunk => {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                cell.textContent = chunk.index;
                
                if (retrievedIndices.has(chunk.index)) {
                    cell.classList.add('retrieved');
                }
                
                cell.title = `Chunk ${chunk.index}: "${chunk.text.substring(0, 120)}..."`;
                cell.addEventListener('click', () => {
                    alert(`Chunk ${chunk.index} Text Content:\n\n${chunk.text}`);
                });
                
                chunksGrid.appendChild(cell);
            });

        } catch (err) {
            console.error(err);
            
            // Remove typing bubble if still present
            const currentTyping = chatHistory.querySelector('#bot-typing-indicator');
            if (currentTyping) currentTyping.remove();

            // Append Error Bubble
            const botErrorBubble = document.createElement('div');
            botErrorBubble.className = 'chat-message bot error-msg';
            botErrorBubble.innerHTML = `
                <div class="card-header-simple">
                    <span class="message-badge danger"><i class="fa-solid fa-circle-xmark"></i> Query Error</span>
                </div>
                <div class="message-content">Error: ${err.message}</div>
            `;
            chatHistory.appendChild(botErrorBubble);
        } finally {
            resetFormState();
            // Scroll to bottom after layout calculations
            setTimeout(() => {
                chatHistory.scrollTop = chatHistory.scrollHeight;
            }, 50);
        }
    }

    function resetFormState() {
        submitBtn.disabled = false;
        queryInput.disabled = false;
        queryInput.value = ''; // Reset user typing line for next message
        queryInput.focus();
    }

    submitBtn.addEventListener('click', submitQuery);
    
    queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitQuery();
    });


    // Drag & Drop Event Listeners for File Upload
    uploadZone.addEventListener('click', () => fileUploadInput.click());

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    fileUploadInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleFile(file);
    });

    async function handleFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        uploadStatus.classList.remove('hidden');
        uploadStatus.className = 'upload-status-bar loading';
        uploadStatus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading and extracting text...';

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || 'Failed to extract text from file');
            }

            const data = await res.json();
            
            // Populate text to textarea
            customText.value = data.text;
            
            // Render success message
            uploadStatus.className = 'upload-status-bar';
            uploadStatus.innerHTML = `<i class="fa-solid fa-circle-check"></i> Loaded <strong>${data.filename}</strong> successfully (${data.word_count} words)`;
            
        } catch (err) {
            console.error(err);
            uploadStatus.className = 'upload-status-bar error';
            uploadStatus.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${err.message}`;
        }
    }

    // Initial Fetch call on startup
    fetchUsecases();
});
