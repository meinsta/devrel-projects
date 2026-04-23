# 🎨 H&M Ad Generation Agent

An AI-powered advertisement creation system that uses H&M product images to generate compelling marketing content with Freepik and Google Gemini.

## 🌟 Features

- **H&M Product Search**: Uses Qdrant vector database with CLIP embeddings to find relevant H&M products
- **AI Image Generation**: Leverages Freepik API to generate stunning ad visuals with product references
- **Intelligent Copywriting**: Uses Google Gemini to create compelling ad copy
- **Complete Workflow**: End-to-end pipeline from query to finished advertisement
- **Web Interface**: Interactive Next.js frontend showcasing the agent workflow
- **Product Dataset**: 1000+ H&M products with images, descriptions, and metadata

## 🏗️ Architecture

```
User Query → Qdrant Search (H&M Products) → Freepik Image Gen → Gemini Copy → Complete Ad
```

### Key Components

1. **Agent (`agent.py`)**: Core logic for creating ads
2. **API Server (`api.py`)**: FastAPI server for the web interface
3. **Frontend (`frontend/`)**: Next.js web interface
4. **H&M Dataset (`hm_dataset.csv`)**: 1001 H&M products with images
5. **Ingestion Script (`scripts/ingest_hm_data.py`)**: Load H&M data into Qdrant

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- API keys for:
  - Qdrant Cloud
  - Freepik API
  - Google Gemini

### Installation

1. **Clone and setup environment**:
```bash
git clone <your-repo>
cd test_freepik_qdrant
```

2. **Create `.env` file**:
```bash
# Qdrant Configuration
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION=hm-products

# AI Model APIs
GEMINI_API_KEY=your_gemini_api_key
FREEPIK_API_KEY=your_freepik_api_key

# Optional: Model Configuration
FREEPIK_MODEL=gemini-2-5-flash-image-preview
TEXT_EMBEDDING_MODEL=Qdrant/clip-ViT-B-32-text
```

3. **Setup H&M Dataset**:

The setup script will download the H&M dataset and ingest it into Qdrant:

```bash
./setup_hm.sh
```

This will:
- Download the H&M dataset (1001 products, ~2.5MB)
- Install Python dependencies
- Ingest product images into Qdrant with CLIP embeddings
- Create the `hm-products` collection

**Manual setup** (if you prefer):
```bash
# Download dataset
curl -L "https://raw.githubusercontent.com/luminati-io/HM-dataset-sample/main/H%26M-dataset-sample.csv" -o hm_dataset.csv

# Install dependencies
pip install -r requirements.txt

# Ingest data
python3 scripts/ingest_hm_data.py hm_dataset.csv --collection hm-products
```

4. **Install frontend dependencies**:
```bash
cd frontend
npm install
cd ..
```

## 💡 Usage

### Run the Agent (Web Interface)

The easiest way is using the start script:

```bash
./start_agent.sh
```

This starts both backend (port 8001) and frontend (port 3001).
Open http://localhost:3001 in your browser.

### Run Manually

1. **Start the API**:
```bash
python api.py
# Server runs on http://localhost:8001
```

2. **Start the frontend** (in another terminal):
```bash
cd frontend
npm run dev
# Frontend runs on http://localhost:3001
```

### Run CLI Agent

You can also run the agent directly from the command line:

```bash
# Basic usage
python agent.py "summer fashion collection"

# With options
python agent.py "winter coats and accessories" --num-products 5
```

## 📁 Project Structure

```
test_freepik_qdrant/
├── agent.py                    # Main ad generation agent logic
├── api.py                      # FastAPI server
├── start_agent.sh              # Startup script
├── setup_hm.sh                 # H&M dataset setup script
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables
├── hm_dataset.csv             # H&M product dataset (1001 products)
│
├── frontend/                   # Next.js web interface
│   ├── app/                    # Next.js app directory
│   └── components/             # React components
│
├── scripts/                    # Utility scripts
│   ├── ingest_hm_data.py      # H&M dataset ingestion
│   ├── verify_setup.py         # Verification script
│   ├── check_collection.py     # Check Qdrant collection
│   └── test_pipeline.py        # Pipeline test script
│
├── history/                    # Generated ad history
└── README.md                   # This file
```

## 🗄️ H&M Dataset

The dataset contains 1001 H&M products with:

- **Product Information**: Name, code, brand, category
- **Images**: High-quality product images (2160px)
- **Metadata**: Description, color, price, category tree
- **Links**: Direct links to H&M product pages

### Dataset Fields

- `product_code`: Unique product identifier
- `product_name`: Product title
- `description`: Detailed product description
- `category`: Product category (e.g., "Lamp Shades", "Men's Jackets")
- `brand`: Always "H&M"
- `color`: Product color
- `final_price`: Current price
- `image_urls`: Array of product image URLs
- `main_image`: Primary product image
- `url`: Link to product page on HM.com

## 🔧 Utilities

- **Verify Setup**: `python scripts/verify_setup.py`
- **Test Pipeline**: `python scripts/test_pipeline.py`
- **Check Collection**: `python scripts/check_collection.py`
- **Re-ingest Data**: `python scripts/ingest_hm_data.py hm_dataset.csv`

## 🔑 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `QDRANT_URL` | Qdrant cluster URL | `https://xyz.qdrant.io` |
| `QDRANT_API_KEY` | Qdrant API key | `your_api_key` |
| `QDRANT_COLLECTION` | Collection name | `hm-products` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |
| `FREEPIK_API_KEY` | Freepik API key | `fp_...` |

## 🎯 How It Works

1. **User enters ad query** (e.g., "summer beach vacation outfit")
2. **Agent analyzes query** with Gemini to create diverse search queries
3. **Vector search** finds relevant H&M products using CLIP image embeddings
4. **Freepik generates** ad image using H&M product images as references
5. **Gemini creates** compelling ad copy (headline, body, CTA)
6. **Complete ad** is assembled and displayed to user
7. **History saved** for future reference

## 📊 Dataset Source

The H&M dataset is from [Bright Data's H&M Dataset Sample](https://github.com/luminati-io/HM-dataset-sample) - a sample of 1001 products from their full 4.1M+ product dataset.

## 📝 License

MIT License

## 🙏 Credits

- **H&M Dataset**: [Bright Data](https://brightdata.com/)
- **Vector Database**: [Qdrant](https://qdrant.tech/)
- **Image Generation**: [Freepik API](https://www.freepik.com/api/)
- **AI Models**: [Google Gemini](https://ai.google.dev/), CLIP embeddings
