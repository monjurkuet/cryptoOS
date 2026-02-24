# API Discovery & Documentation Prompt Template

Use this prompt to discover, test, and document all APIs from any website.

---

## Prompt to Send to AI Assistant

```
I need you to discover, test, and document ALL APIs from [WEBSITE_NAME].

## Your Tasks:

### 1. DISCOVER APIs
- Find all API endpoints (REST, GraphQL, WebSocket)
- Check common locations:
  - /api/*, /v1/*, /v2/* endpoints
  - Network requests in browser DevTools
  - JavaScript bundles for API calls
  - Documentation pages (/docs, /api-docs)
  - Swagger/OpenAPI specs
- Look for:
  - Base URLs (api.example.com, etc.)
  - Authentication requirements
  - Rate limits
  - Request/response formats

### 2. TEST EVERY ENDPOINT
For each endpoint you find:
- Send actual requests
- Capture real response data
- Note HTTP headers (Content-Type, rate limits, caching)
- Test with different parameters
- Verify if authenticated endpoints work without auth

### 3. DOCUMENT EVERYTHING
Create detailed documentation for EACH endpoint with:

## Endpoint Documentation Template

```markdown
# [Endpoint Name]

## Endpoint
```
[METHOD] [FULL_URL]
```

## Request Body/Parameters
```json
{
  "param": "value"
}
```

## Description
[What this endpoint does]

## Response Format
```json
{
  // REAL response from testing
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `field.name` | string | Description |

## Usage
```bash
curl -X [METHOD] "[URL]" -H "Content-Type: application/json" -d '{"param":"value"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None / Required |
| **Rate Limit** | X requests/minute |
| **Response Size** | X KB |
| **Status** | Working / Failed |

## ⚠️ Limitations
- [Any limits discovered]

## 💡 Use Cases
- [What this data is useful for]

## Notes
[Any additional observations]
```

### 4. CREATE SCRIPTS
For each endpoint, create a download script:

```bash
#!/bin/bash
# Download [Endpoint Name]

API_URL="https://api.example.com/[endpoint]"
OUTPUT_FILE="data/[endpoint_name].json"

echo "📥 Downloading [endpoint]..."
curl -s -X [METHOD] "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"param":"value"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
```

### 5. CREATE MASTER DOWNLOAD SCRIPT
```bash
#!/bin/bash
# Download ALL APIs from [WEBSITE]

echo "🚀 Downloading ALL data from [WEBSITE]..."

# Endpoint 1
echo "  📄 [Endpoint 1]..."
curl -s -X POST "..." -o "data/endpoint1.json"

# Endpoint 2
echo "  📄 [Endpoint 2]..."
curl -s -X POST "..." -o "data/endpoint2.json"

# ... add all endpoints

echo ""
echo "✅ All data downloaded!"
ls -lh data/
```

### 6. VERIFY EVERYTHING
- Run each script
- Check output files exist and contain valid JSON
- Document any errors or issues
- Note which endpoints require authentication

## Output Required:

1. **README.md** - Overview of all APIs with quick start guide
2. **docs/** directory with:
   - README.md - Complete API documentation index
   - API_[NAME].md - Detailed docs for EACH endpoint
3. **scripts/** directory with:
   - download_all.sh - Master download script
   - download_[endpoint].sh - Individual scripts for EACH endpoint
4. **data/** - Downloaded sample data

## Requirements:
- Test ALL endpoints with real requests
- Use real response data in documentation
- Include ALL fields with descriptions
- Note limitations and requirements
- Make scripts executable and ready to run
- Everything should be GitHub-ready

Start by exploring the website and finding all API endpoints. Use browser DevTools if needed.
```

---

## Quick Checklist for Manual Discovery

### Check These Sources:
- [ ] Website footer (API links)
- [ ] /docs, /api-docs pages
- [ ] Network tab in DevTools
- [ ] JavaScript source files
- [ ] Swagger/OpenAPI specs
- [ ] GitHub repository
- [ ] Public documentation
- [ ] Community forums

### Key Questions to Answer:
1. What's the base API URL?
2. What authentication is required?
3. What rate limits exist?
4. What formats are supported (JSON, XML)?
5. Are there WebSocket endpoints?
6. What's the response structure?

### Standard Endpoints to Look For:
- `/users` - User data
- `/orders` - Order history
- `/trades` - Trade history
- `/positions` - Open positions
- `/balance` - Wallet balance
- `/ticker` - Price data
- `/orderbook` - Order book
- `/trades` - Recent trades
- `/history` - Transaction history
- `/stats` - Statistics

---

## Example Output Structure

```
project/
├── README.md                          # Main documentation
├── scripts/
│   ├── download_all.sh              # Master script
│   ├── download_endpoint1.sh         # Individual scripts
│   ├── download_endpoint2.sh
│   └── ...
├── docs/
│   ├── README.md                    # API index
│   ├── API_ENDPOINT1.md             # Detailed docs
│   ├── API_ENDPOINT2.md
│   └── ...
├── data/                            # Sample data
├── .gitignore
└── LICENSE
```

---

## Tips for Success

1. **Be Thorough**: Check every network request
2. **Test Everything**: Real requests = real documentation
3. **Document All Fields**: Don't skip anything
4. **Note Limitations**: Rate limits, auth requirements, pagination
5. **Create Executable Scripts**: Ready to run out of the box
6. **Use Real Data**: Examples should be from actual responses
7. **Verify**: Run scripts and check outputs

---

## Copy-Paste Prompt

```
I need you to discover, test, and document ALL APIs from [WEBSITE_URL]. Follow this process:

1. EXPLORE: Find all API endpoints (REST, GraphQL, WebSocket)
2. TEST: Send real requests to every endpoint
3. DOCUMENT: Create detailed docs for EACH endpoint with:
   - Full request/response examples
   - All fields with descriptions
   - Test results and limitations
   - Usage examples
4. SCRIPT: Create bash download scripts for EACH endpoint
5. MASTER: Create a master script to download everything

Output:
- README.md with overview
- docs/API_*.md for each endpoint
- scripts/download_*.sh for each endpoint
- scripts/download_all.sh master script

Be thorough and test everything with real requests.
```
