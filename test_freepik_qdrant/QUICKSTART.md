# 🚀 Quick Start Guide - H&M Ad Generation Agent

This guide will get you up and running with the H&M Ad Generation Agent in just a few minutes.

## ✅ Prerequisites

Before starting, make sure you have:

1. **Python 3.10+** installed
2. **Node.js 18+** installed (for frontend)
3. **API Keys** for:
   - Qdrant Cloud (free tier available at [qdrant.tech](https://qdrant.tech/))
   - Freepik API (get at [freepik.com/api](https://www.freepik.com/api))
   - Google Gemini (get at [ai.google.dev](https://ai.google.dev/))

## 📋 Step-by-Step Setup

### 1. Configure Environment Variables

Create a `.env` file in the project root with your API keys:

```bash
# Copy the template
cp .env.template .env

# Edit .env with your actual API keys
nano .env  # or use your preferred editor
```

Your `.env` should look like:

```bash
# Qdrant Configuration
QDRANT_URL=https://your-cluster-url.qdrant.io
QDRANT_API_KEY=your_actual_qdrant_api_key
QDRANT_COLLECTION=hm-products

# AI Model APIs  
GEMINI_API_KEY=your_actual_gemini_api_key
FREEPIK_API_KEY=your_actual_freepik_api_key

# Optional: Model Configuration
FREEPIK_MODEL=gemini-2-5-flash-image-preview
TEXT_EMBEDDING_MODEL=Qdrant/clip-ViT-B-32-text
```

### 2. Install Dependencies

#### Python Dependencies (Backend)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Setup H&M Dataset

The H&M dataset contains 1001 products with images. You can set it up automatically or manually:

#### Option A: Automatic Setup (Recommended)

```bash
./setup_hm.sh
```

This will:
- Download the H&M dataset (2.5MB CSV)
- Process and embed all product images
- Upload to your Qdrant collection

**Time:** ~10-15 minutes (depending on your internet speed)

#### Option B: Manual Setup

```bash
# 1. Download dataset
curl -L "https://raw.githubusercontent.com/luminati-io/HM-dataset-sample/main/H%26M-dataset-sample.csv" -o hm_dataset.csv

# 2. Activate virtual environment (if not already)
source venv/bin/activate

# 3. Run ingestion
python3 scripts/ingest_hm_data.py hm_dataset.csv --collection hm-products
```

### 4. Verify Setup

Run the verification script to check everything is configured correctly:

```bash
source venv/bin/activate
python3 scripts/verify_setup.py
```

You should see all ✅ checkmarks. If any checks fail, follow the suggestions to fix them.

### 5. Start the Application

#### Option A: Use the start script (Recommended)

```bash
./start_agent.sh
```

This will start both the backend API (port 8001) and frontend (port 3001).

#### Option B: Start manually

Terminal 1 (Backend):
```bash
source venv/bin/activate
python api.py
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

### 6. Use the Application

Open your browser and go to:
```
http://localhost:3001
```

Try some example queries:
- "summer fashion collection"
- "winter coats and jackets"
- "home lighting and decor"
- "casual weekend outfit"

## 🎯 How It Works

1. **You enter a query** (e.g., "summer beach outfit")
2. **Agent analyzes** and creates diverse product searches
3. **Qdrant search** finds relevant H&M products using image embeddings
4. **Freepik generates** a stunning ad image using the products
5. **Gemini writes** compelling ad copy
6. **Complete ad** is displayed with image, headline, body, and CTA

## 🔧 Troubleshooting

### "No module named 'fastembed'"
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Collection 'hm-products' not found"
```bash
source venv/bin/activate
python3 scripts/ingest_hm_data.py hm_dataset.csv
```

### Frontend won't start
```bash
cd frontend
npm install
npm run dev
```

### API connection error
- Check that your `.env` file has the correct Qdrant URL and API key
- Ensure your Qdrant cluster is running
- Test connection: `python3 scripts/verify_setup.py`

## 📚 Next Steps

- **View history**: Check `history/` folder for generated ads
- **Adjust parameters**: Edit `agent.py` to customize behavior
- **Add more products**: Expand the dataset with additional H&M products
- **Customize UI**: Modify `frontend/` to match your brand

## 💡 Tips

- **First run**: The first image generation may take 30-60 seconds
- **Better results**: Use specific queries (e.g., "red summer dress" vs "clothes")
- **Save API costs**: Freepik has rate limits; pace your requests
- **Dataset**: You can ingest more products by expanding the CSV

## 🆘 Need Help?

- Check `README.md` for detailed documentation
- Run `python3 scripts/verify_setup.py` to diagnose issues
- Ensure all environment variables are set correctly
- Check that Qdrant collection has products: `python3 scripts/check_collection.py`

---

**Ready to create amazing ads!** 🎨
