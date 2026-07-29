import os
from flask import Flask, jsonify, request, render_template
from engine.rag_engine import RAGEngine

app = Flask(__name__)

# Data dictionary for all 5 use cases
USE_CASES = {
    "01_interview_prep": {
        "title": "01. Rehearsal Interview Coach",
        "description": "An interview coach helping the candidate rehearse answers about their experience.",
        "persona": "an interview coach helping the candidate rehearse answers about their own experience",
        "default_max_words": 80,
        "default_overlap": 15,
        "default_top_k": 2,
        "queries": [
            "Tell me about a project where you worked with real-time data.",
            "What's a project where you handled payments?",
            "What's your weakest area?"
        ],
        "document": (
            "Candidate Profile & Project Notes:\n\n"
            "1. Real-time Logistics Tracker Project:\n"
            "- Built a cross-platform React Native mobile application that tracks package deliveries in real-time.\n"
            "- Integrated Google Maps API and WebSockets (Socket.io) for live, low-latency driver location updates.\n"
            "- Handles over 1,000 active daily users and reduced delivery query tickets by 25%.\n\n"
            "2. TechCorp Business Intelligence Internship:\n"
            "- Developed an interactive Power BI dashboard tracking sales metrics across 5 global regions.\n"
            "- Designed optimized SQL queries to aggregate and clean daily transaction data from a PostgreSQL database.\n"
            "- Streamlined data pipelines, which improved executive reporting speed by 40%.\n\n"
            "3. Technical Skills:\n"
            "- Languages: Python, JavaScript, SQL, HTML/CSS.\n"
            "- Frameworks & Tools: React Native, React.js, Power BI, Git.\n"
            "- Core Concepts: Retrieval-Augmented Generation (RAG), vector search, relational databases, REST APIs."
        )
    },
    "02_campus_faq": {
        "title": "02. Campus FAQ Helpdesk",
        "description": "A friendly helpdesk assistant answering student inquiries about college policies.",
        "persona": "a friendly campus helpdesk assistant for students",
        "default_max_words": 100,
        "default_overlap": 20,
        "default_top_k": 2,
        "queries": [
            "How many books can I borrow from the library?",
            "Can I enter the hostel at 10 PM on a Saturday?",
            "Can I get into trouble for being late?"
        ],
        "document": (
            "Campus Rules and Regulations Handbook:\n\n"
            "1. Library Borrowing Policy:\n"
            "- Standard students can borrow a maximum of 5 books at any given time.\n"
            "- The loan period is 14 days per book. A late fine of $1.00 per book per day will be charged for overdue items.\n"
            "- Library access is suspended if outstanding fines exceed $10.00.\n\n"
            "2. Hostel Curfew & Entry:\n"
            "- The hostel main gate closes at 9:30 PM on weekdays (Monday to Friday).\n"
            "- On weekends (Saturday and Sunday), the gate closes at 11:00 PM.\n"
            "- Any student arriving after curfew hours without prior written permission from the hostel warden will face disciplinary actions, including parent notification and a $20 fine.\n\n"
            "3. Internal Examination & Attendance:\n"
            "- Students must maintain at least 75% attendance in each subject to qualify for mid-term and end-term examinations.\n"
            "- Absence due to medical emergencies requires an official medical certificate submitted within 3 working days.\n\n"
            "4. Semester Tuition Fee Deadlines:\n"
            "- Tuition fee payments must be cleared by the 10th of the semester-start month.\n"
            "- Payments made between the 11th and 20th incur a late fee of $50.\n"
            "- Non-payment after the 20th results in suspension of student registration."
        )
    },
    "03_study_buddy": {
        "title": "03. OS Revision Study Buddy",
        "description": "A patient study partner helping revision on dense academic Operating System topics.",
        "persona": "a patient study partner helping the student revise for an exam, using simple explanations",
        "default_max_words": 50,
        "default_overlap": 12,
        "default_top_k": 2,
        "queries": [
            "Which scheduling algorithm causes the convoy effect and why?",
            "Why does Round Robin add overhead?"
        ],
        "document": (
            "Operating System CPU Scheduling Notes:\n\n"
            "1. First-Come, First-Served (FCFS) Scheduling:\n"
            "- The CPU is allocated to processes in the exact order they request it.\n"
            "- Non-preemptive algorithm that is simple to write and implement using a FIFO queue.\n"
            "- A major disadvantage is the convoy effect: a single long process running first can delay many short processes waiting behind it, resulting in poor CPU and device utilization.\n\n"
            "2. Shortest-Job-First (SJF) Scheduling:\n"
            "- The CPU is assigned to the process with the smallest next CPU burst.\n"
            "- Optimal algorithm because it yields the absolute minimum average waiting time for a set of processes.\n"
            "- Hard to implement because the length of the next CPU burst cannot be predicted precisely in advance.\n\n"
            "3. Round Robin (RR) Scheduling:\n"
            "- Designed for time-sharing systems, similar to FCFS but preemptive.\n"
            "- Each process gets a small slice of CPU time called a time quantum (typically 10-100 ms) in a circular queue.\n"
            "- While fair, RR introduces system overhead. This overhead comes from frequent context switching, where the system must save the register state of the running process and load the next process's state."
        )
    },
    "04_ecommerce_support": {
        "title": "04. E-Commerce Customer Support",
        "description": "A polite customer support representative for Nomad Backpacks.",
        "persona": "a polite customer support agent for an online backpack store",
        "default_max_words": 80,
        "default_overlap": 15,
        "default_top_k": 2,
        "queries": [
            "Does the backpack fit a 15-inch laptop, and what colors does it come in?",
            "If I return the backpack after 20 days, will I get a refund?"
        ],
        "document": (
            "Nomad Backpack Store - Product and Policy Details:\n\n"
            "1. Product Details (Nomad Pro Backpack):\n"
            "- Laptop Compatibility: Includes a dedicated, padded laptop sleeve that fits up to 16-inch laptops (including 15-inch models).\n"
            "- Available Colors: Comes in Midnight Black, Olive Green, Steel Blue, and Charcoal Gray.\n"
            "- Material & Durability: Made from water-resistant 900D ballistic polyester with reinforced double stitching.\n"
            "- Key Features: USB charging port, anti-theft back pocket, and heavy-duty YKK zippers.\n\n"
            "2. Store Return Policy:\n"
            "- Customers can return purchases within a 15-day window from the delivery date for a full refund.\n"
            "- Items must be in brand new, unused condition with all tags and original packaging intact.\n"
            "- Returns initiated after 15 days from delivery are strictly not eligible for refunds or store credits.\n\n"
            "3. Shipping Information:\n"
            "- Free standard shipping within the continental US for all orders over $75; otherwise, flat rate $4.99.\n"
            "- Express shipping options are available at checkout: 2-Day Shipping for $12.99.\n\n"
            "4. Product Warranty:\n"
            "- Every backpack includes a 2-Year Limited Warranty covering manufacturing defects in materials or craftsmanship (e.g. zipper or strap failure)."
        )
    },
    "05_code_docs": {
        "title": "05. Developer API Docs Assistant",
        "description": "A technical assistant explaining library API and implementation to a developer.",
        "persona": "a precise technical assistant explaining this library's API to a developer",
        "default_max_words": 100,
        "default_overlap": 20,
        "default_top_k": 2,
        "queries": [
            "What does overlap do in chunk_text, and why does it matter?",
            "What does the ask() function return if nothing relevant is found?"
        ],
        "document": (
            "RAGEngine Codebase API Documentation:\n\n"
            "1. Function: RAGEngine._chunk(text: str) -> List[Dict[str, Any]]\n"
            "- Description: Splitting large input text documents into smaller word-based chunks.\n"
            "- Parameters:\n"
            "  * text (str): The input string to chunk.\n"
            "- Class parameters used:\n"
            "  * max_words (int): Maximum words per chunk.\n"
            "  * overlap (int): Word overlap count between adjacent chunks.\n"
            "- Return: A list of dictionaries containing 'index' (0-indexed position) and 'text' (the chunked string).\n"
            "- Importance of overlap: The overlap represents the number of shared words between consecutive chunks. It matters because it prevents loss of semantic context at the boundaries. If a critical detail is split in half across a boundary, overlap ensures it is captured completely in at least one chunk.\n\n"
            "2. Function: RAGEngine.retrieve(query: str, chunks: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]\n"
            "- Description: Searches chunked documents for matches to the user's query.\n"
            "- Parameters:\n"
            "  * query (str): The search phrase or question.\n"
            "  * chunks (List[Dict]): The chunked documents to search within.\n"
            "- Internal logic: Converts chunks to TF-IDF matrix using TfidfVectorizer(stop_words='english') and computes cosine similarity with query's TF-IDF vector.\n"
            "- Class parameters used:\n"
            "  * top_k (int): Specifies how many top-ranking results to return.\n"
            "- Return: Sorted list of tuples: (chunk, cosine_similarity_score), ordered descending by similarity.\n\n"
            "3. Function: RAGEngine.ask(query: str, retrieved_chunks: List[Tuple[Dict, float]], persona: str = None) -> str\n"
            "- Description: Generates a grounded response via Anthropic's Claude 3.5 Sonnet API.\n"
            "- Parameters:\n"
            "  * query (str): User's question.\n"
            "  * retrieved_chunks (List): Selected context chunks from retrieve().\n"
            "  * persona (str, optional): Overrides system behavior with custom tone.\n"
            "- Strictly enforced grounding behavior:\n"
            "  * The LLM must only use facts stated in context.\n"
            "  * If context lacks required info, it returns exactly the fallback string: 'I don't have that information'.\n"
            "  * Each piece of information in the final answer must cite the source using formatting like [Source X]."
        )
    }
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/usecases', methods=['GET'])
def get_usecases():
    return jsonify(USE_CASES)

@app.route('/api/query', methods=['POST'])
def query_rag():
    data = request.get_json() or {}
    usecase_id = data.get("usecase_id")
    query = data.get("query")
    
    if not usecase_id or not query:
        return jsonify({"error": "Missing usecase_id or query"}), 400
        
    # Check if this is a custom upload
    if usecase_id == "custom_upload":
        document_text = data.get("document", "").strip()
        persona = data.get("persona", "a helpful assistant").strip()
        default_max_words = 80
        default_overlap = 15
        default_top_k = 2
        
        if not document_text:
            return jsonify({"error": "No document text provided for custom RAG"}), 400
    else:
        usecase = USE_CASES.get(usecase_id)
        if not usecase:
            return jsonify({"error": "Invalid usecase_id"}), 400
        document_text = usecase["document"]
        persona = usecase["persona"]
        default_max_words = usecase["default_max_words"]
        default_overlap = usecase["default_overlap"]
        default_top_k = usecase["default_top_k"]
        
    # Get custom parameters or use defaults
    max_words = int(data.get("max_words", default_max_words))
    overlap = int(data.get("overlap", default_overlap))
    top_k = int(data.get("top_k", default_top_k))
    
    # Initialize engine with params
    engine = RAGEngine(max_words=max_words, overlap=overlap, top_k=top_k)
    
    # Generate all chunks
    all_chunks = engine._chunk(document_text)
    
    # Perform vector search
    retrieved = engine.retrieve(query, all_chunks)
    
    # Get answer
    answer = engine.ask(query, retrieved, persona=persona)
    
    # Format response
    formatted_retrieved = []
    for chunk, score in retrieved:
        formatted_retrieved.append({
            "index": chunk["index"],
            "text": chunk["text"],
            "score": float(score)
        })
        
    return jsonify({
        "answer": answer,
        "retrieved_chunks": formatted_retrieved,
        "all_chunks": all_chunks,
        "max_words": max_words,
        "overlap": overlap,
        "top_k": top_k
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
